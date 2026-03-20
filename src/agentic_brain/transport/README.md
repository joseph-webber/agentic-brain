# Transport Layer

Real-time communication with multiple transport options.

## Overview

The transport layer provides a unified interface for real-time message delivery with support for:

- **WebSocket** - Fast, bidirectional, native FastAPI
- **Firebase Realtime Database** - Persistent, scalable, cross-device sync
- **Dual-write** - Both transports for maximum reliability

## Quick Start

### WebSocket Only (Default)

```python
from agentic_brain.transport import TransportManager, TransportMode

# In your WebSocket endpoint
@app.websocket("/ws/chat")
async def chat_ws(websocket: WebSocket):
    manager = TransportManager(mode=TransportMode.WEBSOCKET_ONLY)
    await manager.connect(websocket=websocket)
    
    async for message in manager.receive():
        response = process_message(message.content)
        await manager.send(TransportMessage(
            content=response,
            session_id=message.session_id,
            message_id=str(uuid.uuid4()),
        ))
```

### Firebase Only

```python
from agentic_brain.transport import TransportManager, TransportMode, TransportConfig

config = TransportConfig(
    firebase_url="https://your-project.firebaseio.com",
    firebase_credentials="/path/to/credentials.json",
)

manager = TransportManager(config=config, mode=TransportMode.FIREBASE_ONLY)
await manager.connect(session_id="user-123")

# Send message (persisted to Firebase)
await manager.send(TransportMessage(
    content="Hello!",
    session_id="user-123",
    message_id=str(uuid.uuid4()),
))
```

### Dual-Write (Recommended for Production)

```python
# Write to both WebSocket AND Firebase
# WebSocket for instant delivery, Firebase for persistence
manager = TransportManager(mode=TransportMode.DUAL_WRITE)
await manager.connect(websocket=ws, session_id="user-123")

# Message is sent via WebSocket AND stored in Firebase
await manager.send(message)
```

## Transport Modes

| Mode | WebSocket | Firebase | Use Case |
|------|-----------|----------|----------|
| `WEBSOCKET_ONLY` | ✅ Primary | ❌ | Simple chat, low latency |
| `FIREBASE_ONLY` | ❌ | ✅ Primary | Persistence, offline sync |
| `WEBSOCKET_PRIMARY` | ✅ Primary | ✅ Fallback | Speed with backup |
| `FIREBASE_PRIMARY` | ✅ Fallback | ✅ Primary | Persistence with speed |
| `DUAL_WRITE` | ✅ Both | ✅ Both | Maximum reliability |

## Configuration

```python
from agentic_brain.transport import TransportConfig, TransportType

config = TransportConfig(
    # Transport selection
    transport_type=TransportType.WEBSOCKET,
    
    # WebSocket settings
    websocket_url=None,  # Optional custom URL
    
    # Firebase settings
    firebase_url="https://your-project.firebaseio.com",
    firebase_credentials="/path/to/service-account.json",
    
    # Common settings
    timeout=30.0,           # Receive timeout (seconds)
    reconnect_attempts=3,   # Auto-reconnect attempts
    heartbeat_interval=30.0, # Keepalive interval
)
```

### Environment Variables

```bash
# .env
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
FIREBASE_CREDENTIALS=/path/to/credentials.json
```

## API Reference

### TransportMessage

```python
@dataclass
class TransportMessage:
    content: str           # Message content
    session_id: str        # Session identifier
    message_id: str        # Unique message ID
    timestamp: datetime    # UTC timestamp (auto-generated)
    metadata: dict         # Optional metadata
```

### TransportManager

```python
class TransportManager:
    async def connect(websocket=None, session_id=None) -> bool
    async def disconnect() -> None
    async def send(message: TransportMessage) -> bool
    async def receive() -> AsyncIterator[TransportMessage]
    async def send_token(token: str, is_end: bool = False) -> bool
    async def health_check() -> dict
    @property
    def status() -> TransportStatus
```

### TransportStatus

```python
@dataclass
class TransportStatus:
    websocket_connected: bool
    firebase_connected: bool
    active_transport: Optional[TransportType]
    mode: TransportMode
    last_message_at: Optional[datetime]
```

## Firebase Setup

1. Create a Firebase project at https://console.firebase.google.com
2. Enable Realtime Database
3. Create a service account and download credentials JSON
4. Set environment variables or pass to config

### Firebase Rules (Example)

```json
{
  "rules": {
    "sessions": {
      "$session_id": {
        ".read": "auth != null",
        ".write": "auth != null"
      }
    }
  }
}
```

## When to Use Which Transport

| Scenario | Recommended Mode |
|----------|------------------|
| Single-page chat app | `WEBSOCKET_ONLY` |
| Mobile app with offline | `FIREBASE_ONLY` |
| Production chat platform | `DUAL_WRITE` |
| IoT / low-bandwidth | `FIREBASE_ONLY` |
| Gaming / real-time | `WEBSOCKET_ONLY` |
| Multi-device sync | `FIREBASE_PRIMARY` |

## Installation

```bash
# WebSocket only (included by default)
pip install agentic-brain

# With Firebase support
pip install agentic-brain[firebase]

# Everything
pip install agentic-brain[all]
```

## Performance

| Transport | Latency | Throughput | Offline Support |
|-----------|---------|------------|-----------------|
| WebSocket | ~10ms | High | No |
| Firebase | ~100ms | Medium | Yes |
| Dual-write | ~10ms send, ~100ms persist | Medium | Partial |
