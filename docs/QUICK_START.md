# Quick Start

## 1. Install

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install --upgrade pip
pip install -e ".[api,llm]"
```

## 2. Verify the CLI

```bash
ab doctor
ab version
```

## 3. Start the API

```bash
ab serve --host 127.0.0.1 --port 8000
```

## 4. Send your first request

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Hello"}'
```

Expected response shape:

```json
{
  "response": "Echo: Hello",
  "session_id": "sess_...",
  "timestamp": "2026-01-01T12:00:00Z",
  "message_id": "msg_..."
}
```

## 5. Continue the same session

```bash
curl -X POST http://127.0.0.1:8000/chat \
  -H "Content-Type: application/json" \
  -d '{"message": "Tell me more", "session_id": "sess_replace_me"}'
```

## 6. Stream with SSE

```bash
curl -N "http://127.0.0.1:8000/chat/stream?message=Hello&provider=ollama&model=llama3.1:8b"
```

## 7. Try the WebSocket endpoint

`/ws/chat` requires a JWT by default. Generate a token with your app's `JWT_SECRET` and connect with one of these forms:

- `ws://127.0.0.1:8000/ws/chat?token=<jwt>`
- `Authorization: Bearer <jwt>`
- `Sec-WebSocket-Protocol: <jwt>`

## 8. ADL quick check

```bash
agentic adl init --file brain.adl
agentic adl validate --file brain.adl
```

## Where next

- `API_REFERENCE.md`
- `WEBSOCKET_API.md`
- `GRAPHRAG.md`
- `VOICE_GUIDE.md`
- `DEPLOYMENT.md`
