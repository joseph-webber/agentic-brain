# Streaming Support

Real-time LLM streaming is implemented in `src/agentic_brain/streaming/stream_handler.py`.

## What it provides

- Async generators for token streaming
- Chunked response decoding for partial TCP frames
- SSE formatting for browser clients
- WebSocket JSON streaming
- FastAPI `StreamingResponse` wrapper helper

## Public API

```python
from agentic_brain.streaming import StreamingResponse, StreamToken, StreamProvider
```

### Direct streaming

```python
streamer = StreamingResponse(provider="ollama", model="llama3.1:8b")
async for token in streamer.stream("What is AI?"):
    print(token.token, end="")
```

### SSE

```python
return streamer.as_fastapi_response("What is AI?", headers={"X-Session-ID": session_id})
```

### WebSocket

```python
async for payload in streamer.stream_websocket("What is AI?"):
    await websocket.send_text(payload)
```

## Chunked handling

Provider responses may arrive split across multiple network chunks. The stream
handler reassembles text lines before JSON parsing, which avoids broken payloads
when providers flush partial frames.

Helper generators:

- `iter_text_chunks()`
- `iter_chunked_lines()`
- `iter_sse_payloads()`

## API endpoints

- `GET /chat/stream` — SSE chat streaming
- `WebSocket /ws/chat` — bidirectional token streaming

## Testing

Streaming behavior is covered by dedicated unit tests for:

- token serialization
- chunk reassembly
- SSE formatting
- WebSocket formatting
- provider routing
- FastAPI response wrapping
