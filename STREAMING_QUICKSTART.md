# Quick Start: Streaming Chat

Get real-time token-by-token responses in minutes.

## 5-Minute Setup

### 1. Install Dependencies

```bash
pip install "agentic-brain[api]"
# or if already installed, just add:
pip install aiohttp
```

### 2. Start the API Server

```bash
python -m agentic_brain.api.server
# Server running on http://localhost:8000
```

### 3. Stream in Your Browser

Open in any browser:
```
http://localhost:8000/chat/stream?message=Hello%20world
```

You'll see tokens streaming in real-time!

## Common Use Cases

### Python: Direct Streaming

```python
import asyncio
from agentic_brain.streaming import StreamingResponse

async def main():
    streamer = StreamingResponse(
        provider="ollama",
        model="llama3.1:8b"
    )
    
    async for token in streamer.stream("What is AI?"):
        print(token.token, end="", flush=True)
    print()

asyncio.run(main())
```

### Web: Server-Sent Events (SSE)

```javascript
// Streaming in any web browser
const eventSource = new EventSource('/chat/stream?message=Hello');

eventSource.onmessage = (event) => {
    const token = JSON.parse(event.data);
    console.log(token.token);  // Print immediately
};

eventSource.onerror = () => eventSource.close();
```

### Mobile/App: WebSocket

```javascript
// Real-time bidirectional communication
const ws = new WebSocket('ws://localhost:8000/ws/chat');

ws.onopen = () => {
    ws.send(JSON.stringify({
        message: "What is AI?",
        provider: "ollama"
    }));
};

ws.onmessage = (event) => {
    const token = JSON.parse(event.data);
    console.log(token.token);
};
```

## Endpoints

### GET /chat/stream
Stream response as Server-Sent Events.

**Parameters:**
- `message` (required): Your question
- `provider` (optional): "ollama", "openai", or "anthropic"
- `model` (optional): Model name
- `temperature` (optional): 0.0-2.0

**Example:**
```bash
curl "http://localhost:8000/chat/stream?message=Hello&provider=ollama&temperature=0.7"
```

### WebSocket /ws/chat
Real-time bidirectional streaming.

**Send:**
```json
{
    "message": "What is AI?",
    "provider": "ollama",
    "model": "llama3.1:8b",
    "temperature": 0.7
}
```

**Receive:**
```json
{
    "token": "hello",
    "is_start": true,
    "is_end": false,
    "finish_reason": null,
    "metadata": {"provider": "ollama"}
}
```

## Configuration

### Ollama (Local)

```python
streamer = StreamingResponse(
    provider="ollama",
    model="llama3.1:8b",  # or llama2, neural-chat, etc.
)
```

Make sure Ollama is running:
```bash
ollama serve
```

### OpenAI (Cloud)

```python
import os
os.environ['OPENAI_API_KEY'] = 'sk-...'

streamer = StreamingResponse(
    provider="openai",
    model="gpt-4"
)
```

### Anthropic (Cloud)

```python
import os
os.environ['ANTHROPIC_API_KEY'] = 'sk-ant-...'

streamer = StreamingResponse(
    provider="anthropic",
    model="claude-3-sonnet-20240229"
)
```

## Running Examples

```bash
# Run the example with multiple demos
python -m examples.streaming_chat

# This shows:
# - Direct async streaming
# - Streaming with history
# - Provider switching
# - SSE format
# - WebSocket format
# - Lifecycle detection
```

## Real Chat UI Example

Save this as `index.html`:

```html
<!DOCTYPE html>
<html>
<head>
    <title>Streaming Chat</title>
    <style>
        body { font-family: sans-serif; padding: 20px; }
        .container { max-width: 600px; margin: 0 auto; }
        .chat { height: 400px; overflow-y: auto; border: 1px solid #ccc; padding: 10px; margin-bottom: 10px; background: #f9f9f9; }
        .message { margin: 10px 0; padding: 10px; border-radius: 8px; }
        .user { background: #007AFF; color: white; text-align: right; }
        .assistant { background: #e5e5ea; }
        input { width: 80%; padding: 10px; }
        button { padding: 10px 20px; background: #007AFF; color: white; border: none; cursor: pointer; }
    </style>
</head>
<body>
    <div class="container">
        <h1>💬 Streaming Chat</h1>
        <div class="chat" id="chat"></div>
        <input id="input" placeholder="Ask something..." />
        <button onclick="send()">Send</button>
    </div>
    
    <script>
        async function send() {
            const msg = document.getElementById('input').value;
            if (!msg) return;
            
            // Add user message
            document.getElementById('chat').innerHTML += 
                `<div class="message user">${msg}</div>`;
            document.getElementById('input').value = '';
            
            // Stream response
            const res = await fetch(`/chat/stream?message=${encodeURIComponent(msg)}`);
            const reader = res.body.getReader();
            const decoder = new TextDecoder();
            let botMsg = null;
            
            while (true) {
                const {done, value} = await reader.read();
                if (done) break;
                
                const chunk = decoder.decode(value);
                for (const line of chunk.split('\n\n')) {
                    if (line.startsWith('data: ')) {
                        try {
                            const token = JSON.parse(line.slice(6));
                            
                            if (!botMsg) {
                                botMsg = document.createElement('div');
                                botMsg.className = 'message assistant';
                                document.getElementById('chat').appendChild(botMsg);
                            }
                            
                            botMsg.textContent += token.token;
                            document.getElementById('chat').scrollTop = 
                                document.getElementById('chat').scrollHeight;
                        } catch (e) {}
                    }
                }
            }
        }
        
        document.getElementById('input').addEventListener('keypress', (e) => {
            if (e.key === 'Enter') send();
        });
        
        document.getElementById('input').focus();
    </script>
</body>
</html>
```

Open in browser and start chatting!

## Performance

- **First token**: ~100-500ms (depends on model)
- **Subsequent tokens**: ~10-50ms
- **Total response**: Instant start, progressive completion

## Troubleshooting

**"Connection refused" error?**
- Make sure API server is running: `python -m agentic_brain.api.server`
- Check port 8000 is available

**"No tokens appearing?"**
- For Ollama: `ollama serve` must be running
- For cloud: Check API keys are set
- Check internet connection

**"Slow response?"**
- First token delay is normal
- Check your internet speed
- Smaller models are faster

## Next Steps

- Read the full guide: `docs/STREAMING.md`
- Check implementation details: `STREAMING_IMPLEMENTATION.md`
- Explore the examples: `examples/streaming_chat.py`
- Run the tests: `pytest tests/test_streaming.py`

## Need Help?

```bash
# Check the API docs
curl http://localhost:8000/docs

# Run with debug logging
DEBUG=1 python -m agentic_brain.api.server
```

---

That's it! You now have real-time streaming responses. 🚀
