# WebSocket API

The current WebSocket endpoint is implemented in `src/agentic_brain/api/websocket.py`.

## Endpoint

```text
WS /ws/chat
```

## Authentication

WebSocket auth is enforced by default. Supply a JWT using one of these mechanisms:

1. Query parameter: `ws://127.0.0.1:8000/ws/chat?token=<jwt>`
2. Header: `Authorization: Bearer <jwt>`
3. Subprotocol header: `Sec-WebSocket-Protocol: <jwt>`

If the token is missing or invalid, the server closes the connection with policy-violation code `1008`.

## Client message format

```json
{
  "message": "Explain GraphRAG",
  "session_id": "optional_session",
  "user_id": "optional_user",
  "provider": "ollama",
  "model": "llama3.1:8b",
  "temperature": 0.7
}
```

Notes:

- `message` is required.
- `temperature` is coerced to a float; invalid values fall back to `0.7`.
- The current implementation stores recent messages in the legacy in-memory session store used by the WebSocket handler.

## Streamed server messages

The server sends JSON text frames. Successful token frames follow the shape emitted by the streaming backend, for example:

```json
{
  "token": "Hello",
  "is_start": true,
  "is_end": false,
  "finish_reason": null,
  "metadata": {
    "session_id": "sess_...",
    "message_id": "msg_..."
  }
}
```

## Error frames

### Invalid JSON

```json
{
  "type": "error",
  "error": "Invalid JSON",
  "error_code": "INVALID_JSON",
  "token": "",
  "is_end": true,
  "finish_reason": "error"
}
```

### Missing `message`

```json
{
  "type": "error",
  "error": "Missing message field",
  "error_code": "MISSING_MESSAGE",
  "token": "",
  "is_end": true,
  "finish_reason": "error"
}
```

### Internal failure

```json
{
  "type": "error",
  "error": "...",
  "error_code": "INTERNAL_ERROR",
  "token": "",
  "is_end": true,
  "finish_reason": "error"
}
```

## Python example

```python
import asyncio
import json
import jwt
import websockets

JWT_SECRET = "replace-with-your-secret"
token = jwt.encode({"sub": "demo-user"}, JWT_SECRET, algorithm="HS256")

async def main():
    uri = f"ws://127.0.0.1:8000/ws/chat?token={token}"
    async with websockets.connect(uri) as ws:
        await ws.send(json.dumps({"message": "Hello from websockets"}))
        while True:
            frame = json.loads(await ws.recv())
            if frame.get("error"):
                print("error:", frame["error"])
                break
            print(frame.get("token", ""), end="", flush=True)
            if frame.get("is_end"):
                break
        print()

asyncio.run(main())
```

## JavaScript example

```javascript
const token = "replace-with-your-jwt";
const ws = new WebSocket(`ws://127.0.0.1:8000/ws/chat?token=${token}`);

ws.onopen = () => {
  ws.send(JSON.stringify({ message: "Hello from JavaScript" }));
};

ws.onmessage = event => {
  const msg = JSON.parse(event.data);
  if (msg.error) {
    console.error(msg.error);
    return;
  }
  process.stdout.write(msg.token || "");
  if (msg.is_end) process.stdout.write("\n");
};
```

## Verified behavior

The following were verified during this audit with `TestClient`:

- invalid JSON returns `INVALID_JSON`
- missing `message` returns `MISSING_MESSAGE`
- invalid JWT closes the connection before streaming starts
