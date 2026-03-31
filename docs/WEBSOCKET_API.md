# WebSocket API Documentation

Real-time bidirectional streaming chat API for the Agentic Brain platform.

**Table of Contents**
- [Quick Start](#quick-start)
- [Connection Details](#connection-details)
- [Authentication](#authentication)
- [Message Formats](#message-formats)
- [Error Handling](#error-handling)
- [Rate Limiting](#rate-limiting)
- [Connection Management](#connection-management)
- [Client Examples](#client-examples)
- [Advanced Usage](#advanced-usage)
- [Troubleshooting](#troubleshooting)

---

## Quick Start

### Connect and Send Your First Message

```bash
# Using websocat (install: brew install websocat)
websocat ws://localhost:8000/ws/chat

# Then send this JSON:
{"message": "Hello! What is AI?"}

# You'll receive streamed tokens back
```

### Simple Python Example

```python
import asyncio
import websockets
import json

async def main():
    uri = "ws://localhost:8000/ws/chat"
    async with websockets.connect(uri) as ws:
        # Send a message
        await ws.send(json.dumps({"message": "What is machine learning?"}))
        
        # Receive and print streamed response
        while True:
            response = json.loads(await ws.recv())
            if response.get("error"):
                print(f"Error: {response['error']}")
                break
            print(response.get("token", ""), end="", flush=True)
            if response.get("is_end"):
                break
        print()

asyncio.run(main())
```

### Simple JavaScript Example

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onopen = () => {
    ws.send(JSON.stringify({message: "What is AI?"}));
};

ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    if (msg.error) {
        console.error("Error:", msg.error);
        return;
    }
    process.stdout.write(msg.token || "");
    if (msg.is_end) console.log("\nDone!");
};

ws.onerror = (e) => console.error("Error:", e);
ws.onclose = () => console.log("Disconnected");
```

---

## Connection Details

### URL Format

**Development**:
```
ws://localhost:8000/ws/chat
```

**Production**:
```
wss://api.example.com/ws/chat  # (secure WebSocket with TLS)
```

### Protocol Requirements

- **RFC Standard**: RFC 6455 (WebSocket Protocol)
- **Encoding**: UTF-8 JSON
- **Keep-Alive**: Server sends pings every 30 seconds
- **Timeout**: Idle connections closed after 5 minutes
- **Max Message Size**: 32 MB

### Connection Lifecycle

```
1. Client initiates WebSocket handshake
2. Server responds with 101 Switching Protocols
3. Full-duplex connection established
4. Either party can send messages at any time
5. Client sends message request(s)
6. Server streams response token-by-token
7. Either party can initiate close (code 1000)
```

### Headers

Required headers are sent automatically by WebSocket libraries:

```
GET /ws/chat HTTP/1.1
Host: localhost:8000
Upgrade: websocket
Connection: Upgrade
Sec-WebSocket-Key: [random-key]
Sec-WebSocket-Version: 13
```

Optional headers:

```
Authorization: Bearer YOUR_API_KEY  # If authentication enabled
User-Agent: MyClient/1.0
```

---

## Authentication

### No Authentication (Default)

If your server doesn't require authentication, simply connect:

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');
```

### Bearer Token Authentication

If your server requires authentication, include Authorization header:

```javascript
// Note: Some browsers/libraries don't allow setting custom headers
// Use subprotocol instead:
const ws = new WebSocket('ws://localhost:8000/ws/chat', 
    ['authorization', 'Bearer YOUR_API_KEY']
);

// Or pass token in first message:
ws.onopen = () => {
    ws.send(JSON.stringify({
        auth_token: "YOUR_API_KEY",
        message: "What is AI?"
    }));
};
```

### Python with Authentication

```python
import asyncio
import websockets
import json

async def main():
    uri = "ws://localhost:8000/ws/chat"
    headers = {"Authorization": "Bearer YOUR_API_KEY"}
    
    async with websockets.connect(uri, extra_headers=headers) as ws:
        await ws.send(json.dumps({"message": "What is AI?"}))
        while True:
            response = json.loads(await ws.recv())
            print(response.get("token", ""), end="", flush=True)
            if response.get("is_end"):
                break

asyncio.run(main())
```

---

## Message Formats

### Client Request Message

Send JSON from client to server:

```json
{
  "message": "Your question or prompt here",
  "session_id": "chat_abc123xyz",
  "user_id": "user_12345",
  "provider": "ollama",
  "model": "llama3.1:8b",
  "temperature": 0.7
}
```

#### Field Details

| Field | Type | Required | Default | Description |
|-------|------|----------|---------|-------------|
| `message` | string | ✓ Yes | — | The user's question/prompt/message (1-8000 chars) |
| `session_id` | string | No | auto-generated | Session ID for conversation continuity (format: `chat_[alnum]{16}`) |
| `user_id` | string | No | null | User identifier for tracking (1-256 chars) |
| `provider` | string | No | `ollama` | LLM provider: `ollama`, `openai`, `anthropic`, `google` |
| `model` | string | No | `llama3.1:8b` | Model ID (check provider for available models) |
| `temperature` | number | No | `0.7` | Sampling temperature (0.0-2.0, higher = more creative) |

#### Examples

**Minimal Request** (only required field):
```json
{"message": "What is AI?"}
```

**Full Request** (all parameters):
```json
{
  "message": "Explain quantum computing for beginners",
  "session_id": "chat_u8p3n2k1q9w4e5r6",
  "user_id": "user_john_doe_123",
  "provider": "openai",
  "model": "gpt-4",
  "temperature": 1.2
}
```

**Continue Existing Conversation**:
```json
{
  "message": "Tell me more about that",
  "session_id": "chat_u8p3n2k1q9w4e5r6"
}
```

### Server Response (Streamed)

Each streamed token arrives as a separate JSON message:

```json
{
  "token": "Quantum",
  "is_start": true,
  "is_end": false,
  "finish_reason": null,
  "metadata": {
    "session_id": "chat_u8p3n2k1q9w4e5r6",
    "message_id": "msg_k7l8m9n0o1p2q3r4"
  }
}
```

#### Field Details

| Field | Type | Always Present | Description |
|-------|------|---------|-------------|
| `token` | string | ✓ | Text token/chunk (can be 1 char to full word) |
| `is_start` | boolean | ✓ | True only on first token of response |
| `is_end` | boolean | ✓ | True only on final token (stream complete) |
| `finish_reason` | string\|null | ✓ | Why stream ended: `"stop"` (natural), `"length"` (max tokens), `null` (still streaming) |
| `metadata` | object | ✓ | Session and message identifiers |

#### Metadata Fields

```json
{
  "session_id": "chat_u8p3n2k1q9w4e5r6",
  "message_id": "msg_k7l8m9n0o1p2q3r4",
  "response_time_ms": 1234,
  "tokens_generated": 42
}
```

### Full Response Stream Example

For message "Explain AI in 2 sentences":

```
# Token 1 (is_start=true)
{"token": "Artificial", "is_start": true, "is_end": false, "finish_reason": null, "metadata": {...}}

# Token 2
{"token": " Intelligence", "is_start": false, "is_end": false, "finish_reason": null, "metadata": {...}}

# Token 3
{"token": " (AI)", "is_start": false, "is_end": false, "finish_reason": null, "metadata": {...}}

# ... more tokens ...

# Final token (is_end=true)
{"token": ".", "is_start": false, "is_end": true, "finish_reason": "stop", "metadata": {...}}
```

---

## Error Handling

### Error Response Format

```json
{
  "error": "Descriptive error message",
  "token": "",
  "is_end": true,
  "finish_reason": "error",
  "error_code": "ERROR_TYPE",
  "details": {}
}
```

### Error Codes Reference

#### Client Errors (4xx-class)

| Code | HTTP | Description | Solution |
|------|------|-------------|----------|
| `INVALID_JSON` | 400 | Request is not valid JSON | Fix JSON syntax and retry |
| `MISSING_MESSAGE` | 400 | "message" field required but missing | Add "message" field to request |
| `MESSAGE_TOO_LONG` | 413 | Message exceeds 8000 character limit | Shorten message and retry |
| `INVALID_TEMPERATURE` | 400 | Temperature outside 0.0-2.0 range | Use value between 0.0 and 2.0 |
| `INVALID_SESSION_ID` | 400 | Session ID format invalid | Use format `chat_[alnum]{16}` |
| `MODEL_NOT_FOUND` | 404 | Specified model doesn't exist | Check available models and retry |
| `PROVIDER_NOT_SUPPORTED` | 400 | Provider not enabled on this server | Use supported provider |
| `UNAUTHORIZED` | 401 | Authentication failed or missing | Include valid auth token |

#### Server Errors (5xx-class)

| Code | HTTP | Description | Solution |
|------|------|-------------|----------|
| `PROVIDER_ERROR` | 503 | LLM provider error/unavailable | Retry after delay or switch provider |
| `INTERNAL_ERROR` | 500 | Server-side error | See error message, contact support if persistent |
| `TIMEOUT` | 504 | Request took too long | Retry with shorter context or simpler query |
| `RATE_LIMITED` | 429 | Rate limit exceeded | See retry_after field, wait before retrying |

### Error Response Examples

**Invalid JSON**:
```json
{
  "error": "Invalid JSON: Expecting value",
  "token": "",
  "is_end": true,
  "finish_reason": "error",
  "error_code": "INVALID_JSON"
}
```

**Missing Message Field**:
```json
{
  "error": "Missing required field: message",
  "token": "",
  "is_end": true,
  "finish_reason": "error",
  "error_code": "MISSING_MESSAGE"
}
```

**Model Not Found**:
```json
{
  "error": "Model 'gpt-999' not found. Available: gpt-4, gpt-3.5-turbo",
  "token": "",
  "is_end": true,
  "finish_reason": "error",
  "error_code": "MODEL_NOT_FOUND",
  "details": {
    "available_models": ["gpt-4", "gpt-3.5-turbo"]
  }
}
```

**Rate Limited**:
```json
{
  "error": "Rate limit exceeded: 60 messages per minute",
  "token": "",
  "is_end": true,
  "finish_reason": "error",
  "error_code": "RATE_LIMITED",
  "retry_after": 5
}
```

### Error Handling in Code

**Python**:
```python
async with websockets.connect(uri) as ws:
    await ws.send(json.dumps({"message": "What is AI?"}))
    
    while True:
        response = json.loads(await ws.recv())
        
        if response.get("error"):
            error_code = response.get("error_code")
            if error_code == "RATE_LIMITED":
                retry_after = response.get("retry_after", 5)
                print(f"Rate limited. Retry after {retry_after}s")
                return
            elif error_code == "MODEL_NOT_FOUND":
                available = response.get("details", {}).get("available_models", [])
                print(f"Available models: {available}")
                return
            else:
                print(f"Error: {response['error']}")
                return
        
        print(response.get("token", ""), end="", flush=True)
        if response.get("is_end"):
            break
```

**JavaScript**:
```javascript
ws.onmessage = (event) => {
    const msg = JSON.parse(event.data);
    
    if (msg.error) {
        switch (msg.error_code) {
            case "RATE_LIMITED":
                const retryAfter = msg.retry_after || 5;
                console.log(`Rate limited. Retry after ${retryAfter}s`);
                return;
            case "MODEL_NOT_FOUND":
                console.log("Model not found:", msg.error);
                console.log("Available:", msg.details?.available_models);
                return;
            default:
                console.error(`Error (${msg.error_code}):`, msg.error);
                return;
        }
    }
    
    process.stdout.write(msg.token || "");
    if (msg.is_end) console.log("\nDone!");
};
```

---

## Rate Limiting

### Rate Limit Tiers

| Tier | Messages/Minute | Burst | Timeout | Auth Required |
|------|-----------------|-------|---------|---------------|
| Public (no auth) | 10 | 2/10s | 5 min | No |
| Authenticated | 60 | 10/10s | 1 hour | Yes |
| Premium | 300 | 50/10s | 24 hours | Yes |

### Headers in Response

Rate limit info included in response metadata:

```json
{
  "token": "...",
  "metadata": {
    "session_id": "...",
    "rate_limit": {
      "limit": 60,
      "remaining": 45,
      "reset_at": "2024-03-15T12:30:00Z"
    }
  }
}
```

### Handling Rate Limits

When you hit a rate limit, server responds with:

```json
{
  "error": "Rate limit exceeded",
  "error_code": "RATE_LIMITED",
  "retry_after": 5,
  "metadata": {
    "limit_resets_at": "2024-03-15T12:31:00Z",
    "current_usage": 60,
    "limit": 60
  }
}
```

**Recommended Backoff Strategy**:

```python
import asyncio
import random

async def send_with_retry(ws, message, max_retries=3):
    for attempt in range(max_retries):
        try:
            await ws.send(json.dumps(message))
            # Process response...
            return
        except RateLimitError as e:
            if attempt < max_retries - 1:
                # Exponential backoff with jitter
                wait_time = (2 ** attempt) + random.uniform(0, 1)
                print(f"Rate limited. Waiting {wait_time:.1f}s before retry...")
                await asyncio.sleep(wait_time)
            else:
                raise
```

---

## Connection Management

### Keep-Alive / Ping-Pong

Server automatically sends WebSocket ping frames every 30 seconds:

```
Server -> Client: PING frame
Client -> Server: PONG frame (automatic in most libraries)
```

No action needed - your WebSocket library handles this automatically.

### Session Persistence

Sessions are stored server-side for 24 hours:

```
Message 1: {"message": "What is AI?", "session_id": "chat_xyz"}
Response stored with session_id

Disconnect and reconnect later...

Message 2: {"message": "Tell me more", "session_id": "chat_xyz"}
Server retrieves conversation history and continues
```

### Graceful Disconnection

**Client-initiated close**:
```javascript
ws.close(1000, "Normal closure");
```

**Server responds**:
- Echoes close frame back
- Session data preserved
- Resources released

### Idle Timeout

Connections without activity for 5 minutes auto-close:

```
Server detects no activity for 5 minutes
Server closes connection with code 1000
Client should detect close and handle reconnection
```

**Keeping connection alive**:
```python
# Periodically send messages
while True:
    await asyncio.sleep(240)  # Every 4 minutes
    await ws.send(json.dumps({
        "message": "Still here?",
        "session_id": current_session_id
    }))
```

---

## Client Examples

### Python - Full-Featured Client

```python
import asyncio
import websockets
import json
import logging
from datetime import datetime

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class AgenticBrainClient:
    def __init__(self, uri="ws://localhost:8000/ws/chat", session_id=None):
        self.uri = uri
        self.session_id = session_id
        self.ws = None
        self.conversation_history = []
    
    async def connect(self):
        """Connect to WebSocket server"""
        self.ws = await websockets.connect(self.uri)
        logger.info("Connected to Agentic Brain")
    
    async def send_message(self, message, model="llama3.1:8b", temperature=0.7):
        """Send message and get streamed response"""
        request = {
            "message": message,
            "model": model,
            "temperature": temperature
        }
        if self.session_id:
            request["session_id"] = self.session_id
        
        logger.info(f"Sending: {message}")
        await self.ws.send(json.dumps(request))
        
        # Collect response
        response_text = ""
        while True:
            try:
                raw = await asyncio.wait_for(self.ws.recv(), timeout=60)
                data = json.loads(raw)
                
                if data.get("error"):
                    logger.error(f"Error: {data['error']}")
                    return None
                
                token = data.get("token", "")
                response_text += token
                print(token, end="", flush=True)
                
                # Update session ID on first message
                if data.get("is_start") and not self.session_id:
                    self.session_id = data.get("metadata", {}).get("session_id")
                
                if data.get("is_end"):
                    break
            
            except asyncio.TimeoutError:
                logger.error("Response timeout")
                break
        
        print()  # Newline
        self.conversation_history.append({
            "timestamp": datetime.now().isoformat(),
            "user": message,
            "assistant": response_text
        })
        
        return response_text
    
    async def close(self):
        """Close connection"""
        if self.ws:
            await self.ws.close()
            logger.info("Disconnected")

# Usage
async def main():
    client = AgenticBrainClient()
    await client.connect()
    
    try:
        await client.send_message("What is machine learning?")
        await client.send_message("Can you give me an example?")
    finally:
        await client.close()

asyncio.run(main())
```

### JavaScript - React Hook

```javascript
import { useEffect, useRef, useState } from 'react';

export function useChatWebSocket(uri = 'ws://localhost:8000/ws/chat') {
  const ws = useRef(null);
  const [isConnected, setIsConnected] = useState(false);
  const [sessionId, setSessionId] = useState(null);
  const [messages, setMessages] = useState([]);
  const [error, setError] = useState(null);

  useEffect(() => {
    ws.current = new WebSocket(uri);

    ws.current.onopen = () => {
      setIsConnected(true);
      setError(null);
    };

    ws.current.onclose = () => {
      setIsConnected(false);
    };

    ws.current.onerror = (e) => {
      setError(`WebSocket error: ${e}`);
    };

    return () => {
      if (ws.current?.readyState === WebSocket.OPEN) {
        ws.current.close();
      }
    };
  }, [uri]);

  const sendMessage = async (message, model = 'llama3.1:8b') => {
    if (!ws.current || ws.current.readyState !== WebSocket.OPEN) {
      setError('WebSocket not connected');
      return;
    }

    const request = {
      message,
      model,
      ...(sessionId && { session_id: sessionId })
    };

    ws.current.send(JSON.stringify(request));

    let currentResponse = '';
    let messageId;

    return new Promise((resolve, reject) => {
      const onMessage = (event) => {
        try {
          const data = JSON.parse(event.data);

          if (data.error) {
            setError(data.error);
            reject(new Error(data.error));
            return;
          }

          currentResponse += data.token || '';

          if (data.is_start) {
            messageId = data.metadata?.message_id;
            if (!sessionId) {
              setSessionId(data.metadata?.session_id);
            }
          }

          if (data.is_end) {
            setMessages(prev => [...prev, {
              id: messageId,
              role: 'user',
              content: message
            }, {
              id: messageId,
              role: 'assistant',
              content: currentResponse
            }]);

            ws.current?.removeEventListener('message', onMessage);
            resolve(currentResponse);
          }
        } catch (e) {
          reject(e);
        }
      };

      ws.current.addEventListener('message', onMessage);
    });
  };

  return { isConnected, messages, error, sendMessage, sessionId };
}

// Usage in component
export function ChatComponent() {
  const { isConnected, messages, sendMessage, error } = useChatWebSocket();
  const [input, setInput] = useState('');

  const handleSubmit = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    await sendMessage(input);
    setInput('');
  };

  return (
    <div>
      <div className="chat-status">
        {isConnected ? '✓ Connected' : '✗ Disconnected'}
        {error && <span className="error">{error}</span>}
      </div>

      <div className="messages">
        {messages.map((msg, i) => (
          <div key={i} className={`message ${msg.role}`}>
            {msg.content}
          </div>
        ))}
      </div>

      <form onSubmit={handleSubmit}>
        <input
          value={input}
          onChange={(e) => setInput(e.target.value)}
          placeholder="Type your message..."
          disabled={!isConnected}
        />
        <button type="submit" disabled={!isConnected}>Send</button>
      </form>
    </div>
  );
}
```

### curl/websocat Testing

```bash
# Install websocat
brew install websocat  # macOS
# or
cargo install websocat  # any platform

# Connect
websocat ws://localhost:8000/ws/chat

# Type JSON message:
{"message": "What is AI?"}

# Receive response tokens line by line
# Press Ctrl+C to disconnect
```

### Go Example

```go
package main

import (
	"encoding/json"
	"fmt"
	"log"
	"github.com/gorilla/websocket"
)

type ChatMessage struct {
	Message string  `json:"message"`
	Model   string  `json:"model,omitempty"`
	Temp    float64 `json:"temperature,omitempty"`
}

type ChatResponse struct {
	Token      string `json:"token"`
	IsStart    bool   `json:"is_start"`
	IsEnd      bool   `json:"is_end"`
	Error      string `json:"error,omitempty"`
	FinishReason string `json:"finish_reason"`
}

func main() {
	ws, _, err := websocket.DefaultDialer.Dial("ws://localhost:8000/ws/chat", nil)
	if err != nil {
		log.Fatal(err)
	}
	defer ws.Close()

	// Send message
	msg := ChatMessage{
		Message: "What is machine learning?",
		Model:   "llama3.1:8b",
		Temp:    0.7,
	}
	if err := ws.WriteJSON(msg); err != nil {
		log.Fatal(err)
	}

	// Receive response
	for {
		var resp ChatResponse
		if err := ws.ReadJSON(&resp); err != nil {
			log.Fatal(err)
		}

		if resp.Error != "" {
			log.Fatalf("Error: %s", resp.Error)
		}

		fmt.Print(resp.Token)

		if resp.IsEnd {
			fmt.Println("\n[Response complete]")
			break
		}
	}
}
```

---

## Advanced Usage

### Session Management

Maintain conversation across reconnects:

```python
import json

async def maintain_session(client, session_id=None):
    """Manage session across connections"""
    
    # First connection - generate session
    if not session_id:
        response = await client.send_message("Hello")
        session_id = client.session_id
        with open("session.json", "w") as f:
            json.dump({"session_id": session_id}, f)
    
    # Later connection - use saved session
    else:
        # Reconnect with saved session_id
        await client.connect()
        client.session_id = session_id
        response = await client.send_message("Continue from before")
```

### Streaming Multiple Concurrent Requests

```python
async def concurrent_chat():
    """Send multiple messages concurrently (respecting rate limits)"""
    tasks = []
    for i in range(3):
        message = f"Question {i+1}: Tell me about topic {i+1}"
        tasks.append(client.send_message(message))
    
    # Process concurrently but respecting rate limit
    results = await asyncio.gather(*tasks)
    return results
```

### Custom Temperature Profiles

```python
TEMPERATURE_PROFILES = {
    "precise": 0.1,      # Deterministic, factual
    "balanced": 0.7,     # Good mix
    "creative": 1.5,     # Highly creative
    "hallucinate": 2.0   # Maximum creativity (risky!)
}

async def chat_with_profile(message, profile="balanced"):
    temp = TEMPERATURE_PROFILES.get(profile, 0.7)
    return await client.send_message(message, temperature=temp)
```

### Streaming to File

```python
async def stream_to_file(message, output_file):
    """Stream response directly to file"""
    with open(output_file, 'w') as f:
        await client.ws.send(json.dumps({"message": message}))
        
        while True:
            response = json.loads(await client.ws.recv())
            if response.get("error"):
                raise Exception(response["error"])
            
            f.write(response.get("token", ""))
            f.flush()
            
            if response.get("is_end"):
                break
```

---

## Troubleshooting

### Common Issues

#### "Connection refused"
```
Error: Connection refused on ws://localhost:8000/ws/chat

Solution:
1. Verify server is running: ps aux | grep agentic
2. Check port 8000 is listening: lsof -i :8000
3. Check firewall: sudo pfctl -s state | grep 8000
4. Verify correct URL and host
```

#### "Invalid JSON" Error
```
{"error": "Invalid JSON: Expecting value", "error_code": "INVALID_JSON"}

Solution:
- Validate JSON syntax: python -m json.tool your_message.json
- Check for missing quotes: {"message": "text"} ✓
- Ensure UTF-8 encoding
- Example: {'message': 'text'} ✗ (single quotes)
```

#### "Missing message field"
```
{"error": "Missing required field: message", "error_code": "MISSING_MESSAGE"}

Solution:
- Always include "message" field
- Correct: {"message": "Your question"}
- Wrong: {"query": "Your question"}
```

#### "Rate limited" (429)
```
{"error": "Rate limit exceeded: 60/min", "error_code": "RATE_LIMITED", "retry_after": 5}

Solution:
- Wait the number of seconds specified in retry_after
- Reduce message frequency
- Authenticate to get higher limits
- Implement exponential backoff retry logic
```

#### "Model not found"
```
{"error": "Model 'gpt-999' not found", "error_code": "MODEL_NOT_FOUND"}

Solution:
- Query available models endpoint
- Use default: llama3.1:8b
- Check provider availability
- Install additional models locally if using Ollama
```

#### Connection Drops Unexpectedly
```
WebSocket closed with code 1006 (abnormal closure)

Solution:
1. Check server logs: journalctl -u agentic-brain -f
2. Verify network stability
3. Implement auto-reconnect logic
4. Check for idle timeout (>5 minutes): send keepalive messages
5. Monitor resource usage: memory, CPU, open files
```

### Debug Mode

**Enable verbose logging**:

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Now see all WebSocket frames:
# DEBUG: send: b'...'
# DEBUG: recv: b'...'
```

**Monitor with tcpdump**:

```bash
# Capture WebSocket traffic
sudo tcpdump -i lo -s 0 'port 8000' -A | grep -E "^..." -A 5
```

**Server-side diagnostics**:

```python
# Add to server
app.state.debug_mode = True

# Returns detailed error info including:
# - Request body
# - Stack traces
# - Provider responses
```

---

## API Reference Summary

### Quick Reference

```
Connect:  ws://localhost:8000/ws/chat
Send:     {"message": "...", "model": "llama3.1:8b", "temperature": 0.7}
Receive:  {"token": "...", "is_start": bool, "is_end": bool, "finish_reason": str}
Error:    {"error": "...", "error_code": "...", "retry_after": int}
```

### Rate Limits

- **Unauthenticated**: 10/min, burst 2/10s
- **Authenticated**: 60/min, burst 10/10s
- **Premium**: 300/min, burst 50/10s

### Timeout Values

- **Connect timeout**: 30 seconds
- **Read timeout**: 60 seconds per message
- **Idle timeout**: 5 minutes
- **Keep-alive ping**: 30 seconds

### Close Codes

- `1000`: Normal closure
- `1001`: Going away
- `1006`: Abnormal closure (network error)
- `1008`: Policy violation
- `1011`: Server error
- `1012`: Service restart

---

## Support

For issues or questions:

1. Check [Troubleshooting](#troubleshooting) section
2. Review [Error Codes](#error-codes-reference)
3. Check server logs: `journalctl -u agentic-brain -f`
4. Run diagnostics: `agentic-brain --health`
5. File issue with logs and steps to reproduce

---

**Last Updated**: 2024-03-15
**API Version**: 1.0
**WebSocket Version**: RFC 6455
