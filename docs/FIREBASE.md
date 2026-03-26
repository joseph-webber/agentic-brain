# Firebase Integration Guide

> Real-time, cross-device sync with offline support

## Overview

Agentic Brain's Firebase transport provides **production-ready real-time messaging** via Firebase Realtime Database. Perfect for:

- **Cross-device chat** - Sync instantly between mobile, web, desktop
- **Offline-first apps** - Messages queue locally, sync when back online
- **Scalable backends** - Firebase handles millions of concurrent connections
- **Multi-tenant systems** - Session isolation built-in

## Quick Start

### 1. Install

```bash
pip install agentic-brain[firebase]
```

### 2. Firebase Setup

1. Create project at [Firebase Console](https://console.firebase.google.com)
2. Enable **Realtime Database** (not Firestore)
3. Download service account credentials:
   - Project Settings → Service Accounts → Generate New Private Key

### 3. Configure

```bash
export FIREBASE_PROJECT_ID=your-project-id
export FIREBASE_DATABASE_URL=https://your-project-id.firebaseio.com
export FIREBASE_CREDENTIALS_FILE=/path/to/service-account.json
```

### 4. Use

```python
from agentic_brain.transport import FirebaseTransport, TransportConfig
from agentic_brain.transport.firebase_config import load_firebase_config

# Load config from environment
config = load_firebase_config()

# Create transport
transport_config = TransportConfig(
    firebase_url=config.database_url,
    firebase_credentials=config.credentials_file,
)

async with FirebaseTransport(transport_config, session_id="my-session") as transport:
    # Send message
    await transport.send(TransportMessage(
        content="Hello from Python!",
        session_id="my-session",
    ))
    
    # Listen for messages
    async for message in transport.listen():
        print(f"Received: {message.content}")
```

## Features

### Real-Time Streaming

Messages stream instantly via Firebase listeners:

```python
async for message in transport.listen():
    print(f"{message.timestamp}: {message.content}")
```

### Offline Support

Messages queue locally when offline, sync automatically when reconnected:

```python
transport = FirebaseTransport(
    config,
    session_id="my-session",
    enable_offline=True,  # Enable SQLite queue
    auto_reconnect=True,  # Auto-reconnect with backoff
)
```

Offline queue persists to `~/.agentic_brain/firebase_offline.db`.

### Connection State Monitoring

```python
from agentic_brain.transport import ConnectionState

# Check current state
if transport.connection_state == ConnectionState.CONNECTED:
    print("Online!")

# Register callbacks
transport.on_disconnect(lambda: print("Lost connection"))
transport.on_connect(lambda: print("Reconnected"))
```

States: `DISCONNECTED`, `CONNECTING`, `CONNECTED`, `RECONNECTING`, `ERROR`

### Session State Sync

Share state across all connected clients:

```python
# Update state
await transport.update_state({
    "typing": True,
    "last_activity": datetime.now().isoformat(),
})

# Listen for state changes
async for state in transport.receive_state_changes():
    print(f"State updated: {state}")
```

### Message History

Retrieve past messages:

```python
history = await transport.get_history(limit=50)
for msg in history:
    print(f"{msg.timestamp}: {msg.content}")
```

### Statistics

```python
stats = transport.stats
print(f"Sent: {stats.messages_sent}")
print(f"Received: {stats.messages_received}")
print(f"Reconnections: {stats.reconnection_count}")
print(f"Offline queue: {stats.offline_queue_size}")
```

## Configuration Options

### Environment Variables

| Variable | Required | Description |
|----------|----------|-------------|
| `FIREBASE_PROJECT_ID` | Yes | Firebase project ID |
| `FIREBASE_DATABASE_URL` | Yes | Realtime Database URL |
| `FIREBASE_CREDENTIALS_FILE` | Yes* | Path to service account JSON |
| `FIREBASE_API_KEY` | No | Web API key (client auth) |
| `FIREBASE_STORAGE_BUCKET` | No | Storage bucket name |
| `FIREBASE_AUTH_DOMAIN` | No | Auth domain |

*Or use `FIREBASE_CREDENTIALS` or provide `credentials_dict`.

### TransportConfig Options

```python
TransportConfig(
    firebase_url="https://xxx.firebaseio.com",
    firebase_credentials="/path/to/creds.json",
    timeout=30.0,  # Connection timeout
)
```

### FirebaseTransport Options

```python
FirebaseTransport(
    config,
    session_id="unique-session-id",
    enable_offline=True,      # SQLite offline queue
    auto_reconnect=True,      # Auto-reconnect on disconnect
    sync_state=True,          # Sync session state
    max_reconnect_delay=60,   # Max backoff delay (seconds)
)
```

## Database Structure

Messages are stored at:

```
/sessions/{session_id}/messages/{message_id}
/sessions/{session_id}/state
```

### Security Rules

Recommended Firebase security rules:

```json
{
  "rules": {
    "sessions": {
      "$session_id": {
        "messages": {
          ".read": "auth != null",
          ".write": "auth != null",
          "$message_id": {
            ".validate": "newData.hasChildren(['content', 'timestamp'])"
          }
        },
        "state": {
          ".read": "auth != null",
          ".write": "auth != null"
        }
      }
    }
  }
}
```

For development/testing (NOT production):

```json
{
  "rules": {
    ".read": true,
    ".write": true
  }
}
```

## Examples

### Multi-Client Chat

Run in multiple terminals:

```bash
# Terminal 1
export FIREBASE_SESSION_ID=team-chat
python examples/11_firebase_chat.py

# Terminal 2
export FIREBASE_SESSION_ID=team-chat
python examples/11_firebase_chat.py
```

Messages sync instantly between all clients!

### Integration with Agent

```python
from agentic_brain import Agent
from agentic_brain.transport import FirebaseTransport, TransportConfig

# Create agent with Firebase transport
transport = FirebaseTransport(
    TransportConfig(firebase_url=url, firebase_credentials=creds),
    session_id="agent-session",
)

agent = Agent(
    name="assistant",
    instructions="You are a helpful assistant",
    transport=transport,
)

# Messages now sync across devices
async with transport:
    response = await agent.run("Hello!")
```

### Health Monitoring

```python
# Check if transport is healthy
is_healthy = await transport.is_healthy()

# Get connection state
state = transport.connection_state

# Monitor with callbacks
def on_unhealthy():
    send_alert("Firebase connection lost!")

transport.on_disconnect(on_unhealthy)
```

## Troubleshooting

### "Firebase SDK not installed"

```bash
pip install firebase-admin
# or
pip install agentic-brain[firebase]
```

### "Permission denied"

1. Check credentials file path is correct
2. Verify service account has Database Admin role
3. Check security rules allow access

### "Connection timeout"

1. Check `FIREBASE_DATABASE_URL` is correct
2. Verify firewall allows outbound HTTPS
3. Try increasing `timeout` in config

### Messages not syncing

1. Check all clients use same `session_id`
2. Verify Firebase rules allow read/write
3. Check `stats.messages_sent` increases

### Offline queue growing

1. Check internet connectivity
2. Verify credentials haven't expired
3. Monitor `stats.offline_queue_size`

## Best Practices

### Session Management

- Use **unique session IDs** per conversation
- Include **tenant ID** in session for multi-tenant: `tenant123_session456`
- **Clear old sessions** periodically to manage costs

### Performance

- **Batch messages** when possible
- Use **pagination** for history (`limit` parameter)
- **Disconnect** when not actively using

### Security

- **Never expose** service account credentials in client code
- Use **Firebase Authentication** for production
- Set **strict security rules** - never use `".read": true` in production
- **Rotate credentials** regularly

### Cost Management

Firebase Realtime Database pricing:
- **Free tier**: 1GB storage, 10GB/month bandwidth
- **Blaze plan**: Pay as you go

To minimize costs:
- Delete old sessions/messages
- Use efficient data structures
- Monitor usage in Firebase Console

## API Reference

### FirebaseTransport

| Method | Description |
|--------|-------------|
| `send(message)` | Send a message |
| `listen()` | Async iterator for incoming messages |
| `get_history(limit)` | Get message history |
| `update_state(state)` | Update session state |
| `receive_state_changes()` | Async iterator for state changes |
| `is_healthy()` | Check connection health |
| `clear_session()` | Clear all session data |
| `on_connect(callback)` | Register connect callback |
| `on_disconnect(callback)` | Register disconnect callback |

### FirebaseConfig

| Method | Description |
|--------|-------------|
| `validate()` | Validate configuration |
| `to_transport_config_kwargs()` | Get TransportConfig kwargs |
| `to_firebase_options()` | Get Admin SDK options |
| `to_web_config()` | Get web SDK config |

### Functions

| Function | Description |
|----------|-------------|
| `load_firebase_config()` | Load config from environment |
| `validate_credentials_file(path)` | Validate credentials JSON |
| `create_sample_config()` | Generate sample .env content |

---

## Next Steps

- [Transport Architecture](architecture.md)
- [WebSocket Transport](websocket.md)
- [Multi-Tenant Setup](../DEPLOYMENT.md)

---

## Firebase Cloud Messaging (FCM)

Push notifications to mobile and web clients.

### Setup

```python
from agentic_brain.transport import (
    FirebaseMessaging,
    NotificationPayload,
    NotificationPriority,
    NotificationType,
)

# Initialize
fcm = FirebaseMessaging(
    credentials_path="service-account.json",
    project_id="your-project"
)
```

### Send to Device

```python
payload = NotificationPayload(
    title="New Message",
    body="You have a new chat message",
    notification_type=NotificationType.MESSAGE,
    data={"session_id": "abc123"}
)

result = fcm.send_to_device(
    token="device_fcm_token",
    payload=payload,
    priority=NotificationPriority.HIGH
)

if result.success:
    print(f"Sent: {result.message_id}")
else:
    print(f"Failed: {result.error}")
```

### Send to Topic

```python
# All subscribers to "announcements" topic
result = fcm.send_to_topic(
    topic="announcements",
    payload=NotificationPayload(
        title="System Update",
        body="New features available!"
    )
)
```

### Device Token Management

```python
# Register device
device = fcm.register_token(
    token="fcm_token_here",
    device_type="android",  # android, ios, web
    user_id="user-123",
    topics=["news", "alerts"]
)

# Get all user's devices
tokens = fcm.get_user_tokens("user-123")

# Send to all user's devices
result = fcm.send_to_user(
    user_id="user-123",
    payload=NotificationPayload(title="Hello", body="World")
)

# Unregister
fcm.unregister_token("fcm_token_here")
```

### Multicast (Batch Send)

```python
# Send to multiple devices efficiently (up to 500)
tokens = ["token1", "token2", "token3", ...]

result = fcm.send_multicast(
    tokens=tokens,
    payload=NotificationPayload(
        title="Broadcast",
        body="Message for everyone"
    )
)

print(f"Success: {result.success_count}")
print(f"Failed: {result.failure_count}")
```

### Topic Subscriptions

```python
# Subscribe device to topic
fcm.subscribe_to_topic("device_token", "news")

# Unsubscribe
fcm.unsubscribe_from_topic("device_token", "news")

# Conditional send (topic combinations)
result = fcm.send_to_topic(
    topic="news",
    payload=payload,
    condition="'news' in topics && 'premium' in topics"
)
```

### FCM Statistics

```python
stats = fcm.get_stats()

print(f"Total tokens: {stats['total_tokens']}")
print(f"Valid: {stats['valid_tokens']}")
print(f"Android: {stats['by_device_type']['android']}")
print(f"iOS: {stats['by_device_type']['ios']}")
print(f"Topics: {stats['topics']}")

# Cleanup invalid tokens
removed = fcm.cleanup_invalid_tokens()
```

### Notification Types

```python
from agentic_brain.transport import NotificationType

NotificationType.ALERT     # Important alerts
NotificationType.UPDATE    # Status updates
NotificationType.MESSAGE   # Chat messages
NotificationType.REMINDER  # Scheduled reminders
NotificationType.SYSTEM    # System notifications
```

---

## Firebase Emulator Suite

Local development without cloud costs.

### Enable Emulators

```bash
# Start Firebase emulators
firebase emulators:start

# Enable in your app
export FIREBASE_USE_EMULATOR=true
```

### Auto-Configuration

```python
from agentic_brain.transport import (
    FirebaseEmulator,
    setup_emulators,
    use_emulators,
)

# Check if emulators should be used
if use_emulators():
    # Auto-detect and configure running emulators
    results = setup_emulators()
    print(f"Configured: {results}")
```

### Manual Configuration

```python
from agentic_brain.transport import EmulatorConfig, FirebaseEmulator

# Custom ports
config = EmulatorConfig(
    auth_port=9099,
    firestore_port=8080,
    database_port=9000,
    project_id="demo-project"
)

emulator = FirebaseEmulator(config)

# Check what's running
status = emulator.check_status()
print(f"Auth running: {status.auth_running}")
print(f"Firestore running: {status.firestore_running}")

# Configure specific service
if emulator.is_running("firestore"):
    emulator.configure_firestore()
```

### Connection Info

```python
emulator = FirebaseEmulator()
info = emulator.get_connection_info()

print(f"Auth URL: {info['auth']['url']}")
print(f"Firestore: {info['firestore']['url']}")
print(f"Project: {info['project_id']}")
```

### Test Data Helpers

```python
from agentic_brain.transport.firebase_emulator import (
    create_test_user,
    clear_firestore_data,
    clear_auth_users,
)

# Create test user (requires requests library)
user = create_test_user(
    email="test@example.com",
    password="testpass123",
    display_name="Test User"
)

# Clear data between tests
clear_firestore_data()
clear_auth_users()
```

### Environment Variables

| Variable | Description |
|----------|-------------|
| `FIREBASE_USE_EMULATOR` | Enable emulator mode (`true/1/yes`) |
| `FIREBASE_AUTH_EMULATOR_HOST` | Auth emulator (default: `localhost:9099`) |
| `FIRESTORE_EMULATOR_HOST` | Firestore emulator (default: `localhost:8080`) |
| `FIREBASE_DATABASE_EMULATOR_HOST` | RTDB emulator (default: `localhost:9000`) |
| `FIREBASE_STORAGE_EMULATOR_HOST` | Storage emulator (default: `localhost:9199`) |
| `GCLOUD_PROJECT` | Project ID for emulators |

### CI/CD Integration

```yaml
# GitHub Actions example
jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      
      - name: Start Firebase Emulators
        run: |
          npm install -g firebase-tools
          firebase emulators:start --only firestore,auth &
          sleep 5
          
      - name: Run tests
        env:
          FIREBASE_USE_EMULATOR: "true"
        run: pytest tests/
```

---

## Firestore Document Transport

Document-based storage for complex queries.

### Basic Usage

```python
from agentic_brain.transport import FirestoreTransport, TransportConfig

config = TransportConfig(
    firestore_project="your-project",
    firestore_credentials="/path/to/credentials.json"
)

async with FirestoreTransport(config, session_id="session-1") as transport:
    # Send message
    await transport.send(message)
    
    # Listen for messages
    async for msg in transport.listen():
        print(msg.content)
```

### Query Helpers

```python
from agentic_brain.transport import FirestoreQueries

# Create query helper
queries = FirestoreQueries(db, "session-123")

# Get messages by sender
user_msgs = await queries.get_by_sender("user")

# Search messages
results = await queries.search_content("hello")

# Get unread count
unread = await queries.get_unread_count()
```

---

## Complete Feature Matrix

| Feature | Realtime DB | Firestore | FCM | Emulators |
|---------|-------------|-----------|-----|-----------|
| Real-time sync | ✅ | ✅ | - | ✅ |
| Offline support | ✅ | ✅ | - | ✅ |
| Complex queries | ❌ | ✅ | - | ✅ |
| Push notifications | - | - | ✅ | ✅ |
| Topic messaging | - | - | ✅ | - |
| Local development | ✅ | ✅ | ❌ | ✅ |
| Cost-free testing | ❌ | ❌ | ❌ | ✅ |

---

## Unified Transport Interface (ChatFeatures)

The `ChatFeatures` class provides a **single API** that works identically regardless of backend: WebSocket, Firebase, or local-only. This allows you to:

- **Develop locally** with no external services
- **Deploy with WebSocket** for standard server-to-client sync
- **Scale with Firebase** for cross-device, offline-first sync

### Same Code, Any Backend

```python
from agentic_brain.transport import ChatFeatures, TransportType

# Local-only mode (development)
features = ChatFeatures()

# WebSocket mode (standard deployment)
features = ChatFeatures(transport_type=TransportType.WEBSOCKET)

# Firebase mode (production scale)
features = ChatFeatures(
    transport_type=TransportType.FIREBASE,
    firebase_ref=firebase_db.reference()
)

# Same API regardless of backend!
await features.set_online("user123")
await features.start_typing("user123", "chat-room")
await features.track_message("msg1", "sender", "session", ["recipient"])
await features.mark_read("msg1", "recipient")
```

### WebSocket Mode

When using `TransportType.WEBSOCKET`, the system:

1. **Tracks connections** - Maps user IDs to WebSocket connections
2. **Broadcasts changes** - Presence/typing/receipt updates go to all clients
3. **Handles multi-device** - Same user on multiple devices gets all updates
4. **Syncs new clients** - When a client connects, it receives full state

```python
from fastapi import WebSocket
from agentic_brain.transport import ChatFeatures, TransportType

features = ChatFeatures(transport_type=TransportType.WEBSOCKET)

@app.websocket("/chat/{user_id}")
async def chat_websocket(websocket: WebSocket, user_id: str):
    await websocket.accept()
    
    # Add connection (auto-sets user online)
    await features.add_connection(user_id, websocket, auto_online=True)
    
    # Handle messages
    async for data in websocket.iter_json():
        await features.handle_message(websocket, data)
```

### Message Types (WebSocket Protocol)

```json
// Presence
{"type": "presence", "action": "online|away|busy|offline", "user_id": "..."}

// Typing
{"type": "typing", "action": "start|stop", "session_id": "..."}

// Receipts
{"type": "receipt", "action": "delivered|read|read_all", "message_id": "..."}
```

### Feature Comparison

| Feature | Local-Only | WebSocket | Firebase |
|---------|------------|-----------|----------|
| In-memory state | ✅ | ✅ | ✅ |
| Multi-client sync | ❌ | ✅ | ✅ |
| Cross-device | ❌ | Same server | ✅ |
| Offline queue | ❌ | ❌ | ✅ |
| History | ❌ | ❌ | ✅ |
| Persistence | ❌ | ❌ | ✅ |

### Migration Path

Start simple, scale up:

1. **Development**: Use local-only mode (no setup)
2. **MVP**: Add WebSocket for real-time (your server)
3. **Scale**: Switch to Firebase (global, offline-first)

The API stays the same throughout!

---

## Presence System

Real-time online/offline/typing status for chat applications.

### Overview

The presence system tracks:
- **User status** - Online, away, busy, offline
- **Typing indicators** - Who's typing in which session
- **Last seen** - When user was last active
- **Multi-device** - Track presence across devices

### Quick Start

```python
from agentic_brain.transport import PresenceManager, FirebasePresence

# Local-only (no Firebase required)
presence = PresenceManager()

# Or Firebase-backed (syncs to cloud)
presence = FirebasePresence(db_ref, local_only=False)
```

### Setting User Presence

```python
import asyncio

async def main():
    presence = PresenceManager()
    
    # User comes online
    user = await presence.set_online("user123", device_id="mobile")
    print(f"User is {user.status.value}")  # "online"
    
    # User goes away
    await presence.set_away("user123")
    
    # User is busy
    await presence.set_busy("user123")
    
    # User goes offline
    await presence.set_offline("user123")
    
    # Keep session alive
    await presence.heartbeat("user123")  # or .touch("user123")

asyncio.run(main())
```

### Typing Indicators

```python
async def handle_typing(presence, user_id, session_id):
    # User started typing
    typing = await presence.start_typing(user_id, session_id)
    print(f"{user_id} is typing...")
    
    # Get who's typing in a session
    typers = presence.get_typing(session_id)
    for t in typers:
        print(f"{t.user_id} started typing at {t.started_at}")
    
    # User stopped typing
    await presence.stop_typing(user_id, session_id)
```

### Presence Callbacks

```python
# React to presence changes
async def on_user_status_change(user_id: str, old_status, new_status):
    print(f"{user_id}: {old_status} → {new_status}")

presence.on_presence_change(on_user_status_change)

# React to typing
def on_typing(user_id: str, session_id: str, is_typing: bool):
    if is_typing:
        print(f"{user_id} is typing in {session_id}")

presence.on_typing_change(on_typing)
```

### Presence Stats

```python
stats = presence.get_stats()
print(f"Online: {stats['online']}")
print(f"Away: {stats['away']}")
print(f"Busy: {stats['busy']}")
print(f"Offline: {stats['offline']}")
print(f"Total: {stats['total']}")
```

### Firebase Integration

```python
from agentic_brain.transport import FirebasePresence
import firebase_admin.db as db

# Get Firebase reference
ref = db.reference("presence")

# Create Firebase-backed presence
presence = FirebasePresence(ref, local_only=False)

# All local methods work, plus Firebase sync
await presence.set_online("user123")
# Automatically synced to Firebase Realtime Database
```

### Configuration

```python
from agentic_brain.transport import PresenceManager

presence = PresenceManager(
    timeout_seconds=300,      # Auto-offline after 5 minutes
    typing_timeout=5.0,       # Typing indicator expires after 5 seconds
    auto_cleanup=True,        # Background cleanup of stale presence
)
```

---

## Read Receipts

Track message delivery and read status.

### Overview

Read receipts track:
- **Message status** - Sending, sent, delivered, read, failed
- **Per-user reads** - Who read the message and when
- **Unread counts** - Messages awaiting read by each user
- **Session messages** - All messages in a conversation

### Quick Start

```python
from agentic_brain.transport import ReadReceiptManager, FirebaseReadReceipts

# Local-only
receipts = ReadReceiptManager()

# Or Firebase-backed
receipts = FirebaseReadReceipts(db_ref, local_only=False)
```

### Message Lifecycle

```python
import asyncio

async def send_message(receipts, message_id, sender_id, session_id, recipient_ids):
    # 1. Track message before sending
    await receipts.track_message(
        message_id=message_id,
        session_id=session_id,
        sender_id=sender_id,
        recipient_ids=recipient_ids
    )
    
    # 2. Mark as sent after server confirms
    await receipts.mark_sent(message_id)
    
    # 3. Mark as delivered when recipients receive
    for recipient in recipient_ids:
        await receipts.mark_delivered(message_id)
        break  # Any recipient delivery marks it delivered
    
    # 4. Mark as read when opened
    for reader_id in recipient_ids:
        await receipts.mark_read(message_id, reader_id)
```

### Checking Message Status

```python
# Get full message info
info = receipts.get_message_info(message_id)
if info:
    print(f"Status: {info.status.value}")
    print(f"Sent at: {info.sent_at}")
    print(f"Delivered at: {info.delivered_at}")
    print(f"Read by: {list(info.read_by.keys())}")
```

### Unread Counts

```python
# Get unread count for a user
count = receipts.get_unread_count("user123")
print(f"You have {count} unread messages")

# Get actual unread messages
unread = receipts.get_unread_messages("user123")
for msg_info in unread:
    print(f"Unread: {msg_info.message_id} from {msg_info.sender_id}")

# Mark all as read
await receipts.mark_all_read("user123", "session456")
```

### Receipt Callbacks

```python
# React to status changes
def on_status(message_id: str, old_status, new_status):
    print(f"Message {message_id}: {old_status} → {new_status}")

receipts.on_status_change(on_status)

# React to reads
async def on_read(message_id: str, reader_id: str):
    print(f"{reader_id} read message {message_id}")

receipts.on_read(on_read)
```

### Receipt Stats

```python
stats = receipts.get_stats()
print(f"Total messages: {stats['total']}")
print(f"Pending: {stats['pending']}")
print(f"Sent: {stats['sent']}")
print(f"Delivered: {stats['delivered']}")
print(f"Read: {stats['read']}")
print(f"Failed: {stats['failed']}")
```

### Firebase Integration

```python
from agentic_brain.transport import FirebaseReadReceipts
import firebase_admin.db as db

ref = db.reference("receipts")
receipts = FirebaseReadReceipts(ref, local_only=False)

# All operations sync to Firebase
await receipts.track_message("msg1", "session1", "sender1", ["recipient1"])
await receipts.mark_sent("msg1")
# Status automatically synced to cloud
```

---

## Complete Chat Example

Combining all Firebase features:

```python
import asyncio
from agentic_brain.transport import (
    FirebaseTransport,
    FirebasePresence,
    FirebaseReadReceipts,
    TransportConfig,
)
import firebase_admin
from firebase_admin import credentials, db

# Initialize Firebase
cred = credentials.Certificate("service-account.json")
firebase_admin.initialize_app(cred, {
    "databaseURL": "https://your-project.firebaseio.com"
})

# Create components
transport = FirebaseTransport(TransportConfig(...))
presence = FirebasePresence(db.reference("presence"))
receipts = FirebaseReadReceipts(db.reference("receipts"))

async def chat_app():
    user_id = "user123"
    session_id = "chat-room-1"
    
    # 1. User comes online
    await presence.set_online(user_id, device_id="web")
    
    # 2. Set up typing indicator
    async def handle_input():
        await presence.start_typing(user_id, session_id)
        # ... user types ...
        await presence.stop_typing(user_id, session_id)
    
    # 3. Send a message
    message_id = "msg-uuid-here"
    recipient_ids = ["user456", "user789"]
    
    await receipts.track_message(
        message_id, session_id, user_id, recipient_ids
    )
    
    await transport.send({
        "id": message_id,
        "content": "Hello everyone!",
        "sender": user_id,
        "recipients": recipient_ids,
    })
    
    await receipts.mark_sent(message_id)
    
    # 4. Keep session alive
    while True:
        await presence.heartbeat(user_id)
        await asyncio.sleep(60)

asyncio.run(chat_app())
```

---

## API Reference - Presence

### PresenceStatus

```python
class PresenceStatus(Enum):
    ONLINE = "online"
    AWAY = "away"
    BUSY = "busy"
    OFFLINE = "offline"
```

### PresenceManager Methods

| Method | Description |
|--------|-------------|
| `set_online(user_id, device_id)` | Set user online |
| `set_away(user_id)` | Set user away |
| `set_busy(user_id)` | Set user busy |
| `set_offline(user_id)` | Set user offline |
| `heartbeat(user_id)` | Update last seen timestamp |
| `touch(user_id)` | Alias for heartbeat |
| `get_presence(user_id)` | Get user's presence info |
| `get_all_presence()` | Get all users' presence |
| `start_typing(user_id, session_id)` | Start typing indicator |
| `stop_typing(user_id, session_id)` | Stop typing indicator |
| `get_typing(session_id)` | Get who's typing |
| `on_presence_change(callback)` | Register presence callback |
| `on_typing_change(callback)` | Register typing callback |
| `get_stats()` | Get presence statistics |

---

## API Reference - Read Receipts

### MessageStatus

```python
class MessageStatus(Enum):
    SENDING = "sending"    # Being sent
    SENT = "sent"          # Server confirmed
    DELIVERED = "delivered"  # At least one recipient received
    READ = "read"          # At least one recipient read
    FAILED = "failed"      # Send failed
```

### ReadReceiptManager Methods

| Method | Description |
|--------|-------------|
| `track_message(msg_id, session_id, sender_id, recipient_ids)` | Start tracking |
| `mark_sent(message_id)` | Mark as sent |
| `mark_delivered(message_id)` | Mark as delivered |
| `mark_read(message_id, reader_id)` | Mark as read by user |
| `mark_failed(message_id, error)` | Mark as failed |
| `get_message_info(message_id)` | Get message info |
| `get_unread_messages(user_id)` | Get user's unread messages |
| `get_unread_count(user_id)` | Count unread messages |
| `mark_all_read(user_id, session_id)` | Mark all as read |
| `get_session_messages(session_id)` | Get session's messages |
| `on_status_change(callback)` | Register status callback |
| `on_read(callback)` | Register read callback |
| `get_stats()` | Get receipt statistics |
