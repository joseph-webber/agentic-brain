# Streaming Response Support

Real-time token-by-token streaming for instant UX. Responses feel immediate with tokens arriving as they're generated.

## Features

✅ **Multi-provider support**
- Ollama (local)
- OpenAI (cloud)
- Anthropic (cloud)

✅ **Multiple interfaces**
- Direct async streaming
- Server-Sent Events (SSE) for web
- WebSocket for bidirectional communication

✅ **Production-ready**
- Error handling
- Conversation history support
- Stream lifecycle detection
- Metadata tracking

## Quick Start

### Direct Streaming

```python
from agentic_brain.streaming import StreamingResponse

streamer = StreamingResponse(
    provider="ollama",
    model="llama3.1:8b",
    temperature=0.7,
)

async for token in streamer.stream("What is AI?"):
    print(token.token, end="", flush=True)
```

### FastAPI SSE Endpoint

```python
from fastapi import FastAPI
from fastapi.responses import StreamingResponse as FastAPIStreamingResponse
from agentic_brain.streaming import StreamingResponse

app = FastAPI()

@app.get("/chat/stream")
async def stream_chat(message: str):
    streamer = StreamingResponse(provider="ollama")
    return FastAPIStreamingResponse(
        streamer.stream_sse(message),
        media_type="text/event-stream"
    )
```

### WebSocket Streaming

```python
from fastapi import WebSocket
from agentic_brain.streaming import StreamingResponse

@app.websocket("/ws/chat")
async def websocket_chat(websocket: WebSocket):
    await websocket.accept()
    streamer = StreamingResponse(provider="ollama")
    
    async for token in streamer.stream_websocket("Hello!"):
        await websocket.send_text(token)
```

## Providers

### Ollama (Local)

Perfect for development and private deployments.

```python
streamer = StreamingResponse(
    provider="ollama",
    model="llama3.1:8b",
    api_base="http://localhost:11434",  # Default
)
```

Requires: `ollama pull llama3.1:8b` (or your preferred model)

### OpenAI

For GPT models.

```python
streamer = StreamingResponse(
    provider="openai",
    model="gpt-4",
    api_key="sk-...",  # or set OPENAI_API_KEY env var
)
```

### Anthropic

For Claude models.

```python
streamer = StreamingResponse(
    provider="anthropic",
    model="claude-3-sonnet-20240229",
    api_key="sk-ant-...",  # or set ANTHROPIC_API_KEY env var
)
```

## API Reference

### StreamingResponse

Main class for streaming LLM responses.

```python
class StreamingResponse:
    def __init__(
        self,
        provider: str = "ollama",
        model: str = "llama3.1:8b",
        temperature: float = 0.7,
        max_tokens: int = 1024,
        system_prompt: Optional[str] = None,
        api_key: Optional[str] = None,
        api_base: Optional[str] = None,
    ):
        """Initialize streaming response."""
```

### Methods

#### `stream(message, conversation_history)`

Stream tokens as an async generator.

```python
async for token in streamer.stream("Hello!"):
    print(token.token, end="", flush=True)
```

**Yields**: `StreamToken` objects

#### `stream_sse(message, conversation_history)`

Stream as Server-Sent Events format.

```python
async for sse_line in streamer.stream_sse("Hello!"):
    yield sse_line  # Send to client
```

**Yields**: SSE formatted strings ready for `text/event-stream` response

#### `stream_websocket(message, conversation_history)`

Stream as JSON for WebSocket clients.

```python
async for json_line in streamer.stream_websocket("Hello!"):
    await websocket.send_text(json_line)
```

**Yields**: JSON formatted token strings

### StreamToken

Represents a single token in the stream.

```python
@dataclass
class StreamToken:
    token: str                          # The actual text
    finish_reason: Optional[str]        # 'stop', 'length', 'error'
    is_start: bool                      # True for first token
    is_end: bool                        # True for last token
    metadata: Dict[str, Any]            # provider, model, timing, etc.
    
    def to_dict(self) -> Dict:          # Convert to dict
    def to_sse(self) -> str:            # Convert to SSE format
```

### StreamProvider

Enum of supported providers.

```python
from agentic_brain.streaming import StreamProvider

provider = StreamProvider.OLLAMA
provider = StreamProvider.OPENAI
provider = StreamProvider.ANTHROPIC
```

## Usage Examples

### Example 1: Direct Async Streaming

```python
import asyncio
from agentic_brain.streaming import StreamingResponse

async def main():
    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b"
    )
    
    async for token in streamer.stream("Explain quantum computing"):
        print(token.token, end="", flush=True)
    print()

asyncio.run(main())
```

### Example 2: Conversation with History

```python
history = [
    {"role": "user", "content": "What is AI?"},
    {"role": "assistant", "content": "AI is artificial intelligence..."},
]

streamer = StreamingResponse(provider="ollama")

# Stream response with context
async for token in streamer.stream("Tell me more", history):
    print(token.token, end="", flush=True)
```

### Example 3: Stream Lifecycle Detection

```python
async for token in streamer.stream("Hello"):
    if token.is_start:
        print("🚀 Stream started")
    
    print(token.token, end="", flush=True)
    
    if token.is_end:
        print(f"\n✅ Stream ended: {token.finish_reason}")
        print(f"   Provider: {token.metadata['provider']}")
```

### Example 4: Web Frontend (HTML/JavaScript)

```html
<script>
async function streamChat(message) {
    const response = await fetch(`/chat/stream?message=${encodeURIComponent(message)}`);
    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    
    while (true) {
        const {done, value} = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n\n');
        
        for (const line of lines) {
            if (line.startsWith('data: ')) {
                const token = JSON.parse(line.slice(6));
                document.body.textContent += token.token;
            }
        }
    }
}

// Start streaming
streamChat("What is AI?");
</script>
```

### Example 5: WebSocket Client (JavaScript)

```javascript
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onmessage = (event) => {
    const token = JSON.parse(event.data);
    console.log(token.token);  // Print token immediately
};

// Send message
ws.send(JSON.stringify({
    message: "What is AI?",
    provider: "ollama",
    model: "llama3.1:8b"
}));
```

## REST API Endpoints

### GET /chat/stream

Stream chat response as Server-Sent Events.

**Query Parameters:**
- `message` (required): User message
- `session_id` (optional): Session identifier
- `user_id` (optional): User identifier
- `provider` (optional, default="ollama"): LLM provider
- `model` (optional, default="llama3.1:8b"): Model name
- `temperature` (optional, default=0.7): Sampling temperature

**Response:** `text/event-stream`

```bash
curl "http://localhost:8000/chat/stream?message=Hello"
```

Output:
```
data: {"token": "Hi", "is_start": true, ...}

data: {"token": " there", "is_start": false, ...}

data: {"token": "!", "is_start": false, "is_end": true, ...}

```

### WebSocket /ws/chat

Stream chat response via WebSocket.

**Message Format (client → server):**
```json
{
    "message": "What is AI?",
    "session_id": "sess_123",  // optional
    "user_id": "user_123",     // optional
    "provider": "ollama",      // optional
    "model": "llama3.1:8b",    // optional
    "temperature": 0.7         // optional
}
```

**Response Format (server → client):**
```json
{
    "token": "hello",
    "is_start": false,
    "is_end": false,
    "finish_reason": null,
    "metadata": {
        "provider": "ollama",
        "model": "llama3.1:8b"
    }
}
```

## Configuration

### Environment Variables

```bash
# Ollama
export OLLAMA_API_BASE=http://localhost:11434

# OpenAI
export OPENAI_API_KEY=sk-...

# Anthropic
export ANTHROPIC_API_KEY=sk-ant-...
```

### Custom Configuration

```python
streamer = StreamingResponse(
    provider="ollama",
    model="llama3.1:8b",
    temperature=0.8,           # Higher = more creative
    max_tokens=2048,           # Maximum response length
    system_prompt="You are...", # Custom system message
    api_base="http://custom:11434",  # Custom API endpoint
)
```

## Firebase Transport

For real-time mobile/web apps, use Firebase Realtime Database as a transport layer.

### Configuration

```bash
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
FIREBASE_CREDENTIALS=/path/to/firebase-credentials.json
```

### Usage

```python
from agentic_brain.streaming import FirebaseTransport

transport = FirebaseTransport(
    database_url="https://your-project.firebaseio.com",
    credentials_path="/path/to/credentials.json"
)

# Stream to Firebase path
async for token in streamer.stream("Hello"):
    await transport.push(f"/chats/{session_id}/tokens", token.to_dict())
```

### Client-Side (JavaScript)

```javascript
import { getDatabase, ref, onChildAdded } from 'firebase/database';

const db = getDatabase();
const tokensRef = ref(db, `/chats/${sessionId}/tokens`);

onChildAdded(tokensRef, (snapshot) => {
  const token = snapshot.val();
  document.body.textContent += token.token;
});
```

## Error Handling

Errors are returned as `StreamToken` objects with `finish_reason="error"`:

```python
async for token in streamer.stream("Hello"):
    if token.finish_reason == "error":
        error = token.metadata.get('error', 'Unknown error')
        error_type = token.metadata.get('error_type', 'StreamError')
        print(f"Error ({error_type}): {error}")
        
        # Handle specific errors
        if "rate_limit" in error.lower():
            await asyncio.sleep(60)  # Wait and retry
        elif "timeout" in error.lower():
            # Retry with shorter timeout
            pass
            
    elif token.finish_reason == "length":
        print("Reached max token limit")
        # Response was truncated - may need to continue
        
    elif token.finish_reason == "stop":
        print("Response complete")
```

### Common Error Types

| Error | Cause | Solution |
|-------|-------|----------|
| `ConnectionError` | Provider not running | Start Ollama/check API |
| `AuthenticationError` | Invalid API key | Check credentials |
| `RateLimitError` | Too many requests | Wait and retry |
| `TimeoutError` | Response too slow | Increase timeout |
| `ModelNotFoundError` | Invalid model name | Check model exists |

### Graceful Degradation

```python
async def chat_with_fallback(message: str):
    providers = ["ollama", "openai", "anthropic"]
    
    for provider in providers:
        try:
            streamer = StreamingResponse(provider=provider)
            response = []
            async for token in streamer.stream(message):
                response.append(token.token)
                if token.finish_reason == "error":
                    raise Exception(token.metadata.get("error"))
            return "".join(response)
        except Exception as e:
            print(f"{provider} failed: {e}, trying next...")
            continue
    
    raise Exception("All providers failed")
```

## Performance Tips

1. **Minimize delay to first token**: Stream starts instantly
2. **Progressive rendering**: Update UI with each token
3. **Batch history**: Keep conversation history reasonable (last 10-20 messages)
4. **Use appropriate temperature**: Lower (0.3-0.5) for consistency, higher (0.8-1.5) for creativity
5. **Stream timeouts**: Set reasonable timeouts (default 300s)
6. **Connection reuse**: Reuse `StreamingResponse` instances

## Testing

```bash
# Install development dependencies
pip install ".[dev,api]"

# Run examples
python -m examples.streaming_chat

# Run tests
pytest tests/test_streaming.py -v
```

## Browser Integration

See `examples/streaming_chat.py` for a complete browser example with:
- Real-time chat UI
- Token-by-token display
- Stream lifecycle indicators
- Error handling

## Troubleshooting

**No tokens appearing?**
- Ensure provider is running (Ollama: `ollama serve`)
- Check API keys for cloud providers
- Verify network connectivity

**Slow initial response?**
- Normal for LLMs - first token delay is expected
- Subsequent tokens should stream quickly
- Check model size matches hardware

**WebSocket connection refused?**
- Ensure WebSocket support in your server
- Check CORS settings
- Verify server is running

**Stream hangs indefinitely?**
- Check `max_tokens` setting
- Verify model is responding
- Check for network issues

**SSE not working in Safari?**
- Safari requires specific headers
- Ensure `Content-Type: text/event-stream`
- Check for proxy buffering

---

## See Also

- [api-reference.md](./api-reference.md) — REST API documentation
- [configuration.md](./configuration.md) — Environment variables
- [DEPLOYMENT.md](./DEPLOYMENT.md) — Production deployment

---

## License

Apache-2.0

See LICENSE file for details.
