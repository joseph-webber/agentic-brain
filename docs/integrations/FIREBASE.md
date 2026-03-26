# 🔥 Firebase Integration Guide

> **Real-time sync, offline-first, infinite scale**

Firebase gives Agentic Brain superpowers for cross-device, real-time AI applications that work offline and scale automatically.

---

## 🌟 Why Firebase + Agentic Brain?

| Capability | What It Enables |
|------------|-----------------|
| **Realtime Database** | Instant cross-device message sync (<50ms) |
| **Firestore** | Document storage for agent state, conversations, RAG |
| **Firebase Auth** | Drop-in authentication (Google, Apple, email, anonymous) |
| **Cloud Functions** | Serverless agent endpoints |
| **Offline Support** | Works without internet, syncs when reconnected |
| **Global CDN** | <100ms response worldwide via Firebase Hosting |

---

## 📦 Installation

```bash
# With Firebase support
pip install agentic-brain[firebase]

# Or full install
pip install agentic-brain[all]
```

---

## ⚡ Quick Start

### 1. Firebase Project Setup

1. Go to [Firebase Console](https://console.firebase.google.com)
2. Create new project (or use existing)
3. Enable **Realtime Database** AND/OR **Firestore**
4. Download service account key:
   - ⚙️ Project Settings → Service Accounts → Generate New Private Key
5. Save as `firebase-credentials.json`

### 2. Environment Configuration

```bash
# .env file
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_DATABASE_URL=https://your-project-id.firebaseio.com
FIREBASE_CREDENTIALS_FILE=/path/to/firebase-credentials.json
```

### 3. Basic Usage

```python
from agentic_brain import Agent
from agentic_brain.transport import FirebaseTransport, TransportConfig

# Create Firebase transport
config = TransportConfig(
    firebase_url="https://your-project.firebaseio.com",
    firebase_credentials="/path/to/credentials.json"
)

# Connect agent to Firebase
async with FirebaseTransport(config, session_id="user-123") as transport:
    agent = Agent("assistant", transport=transport)
    
    # Messages now sync in real-time across all connected clients!
    response = await agent.chat("What's the weather like?")
```

---

## 🔄 Realtime Database Transport

The primary transport for real-time chat and messaging:

```python
from agentic_brain.transport import FirebaseTransport, TransportMessage

async with FirebaseTransport(config, session_id="session-abc") as transport:
    # Send a message
    await transport.send(TransportMessage(
        content="Hello from Python!",
        role="user",
        session_id="session-abc"
    ))
    
    # Listen for all messages (real-time stream)
    async for message in transport.listen():
        print(f"[{message.role}]: {message.content}")
```

### Message Structure

```json
{
  "id": "msg-uuid-1234",
  "content": "User's message here",
  "role": "user|assistant|system",
  "session_id": "session-abc",
  "timestamp": 1710000000000,
  "metadata": {
    "tokens": 150,
    "model": "gpt-4o",
    "latency_ms": 245
  }
}
```

### Database Rules (Secure)

```json
{
  "rules": {
    "sessions": {
      "$sessionId": {
        ".read": "auth != null && auth.uid == $sessionId.split('_')[0]",
        ".write": "auth != null && auth.uid == $sessionId.split('_')[0]",
        "messages": {
          ".indexOn": ["timestamp"]
        }
      }
    }
  }
}
```

---

## 📄 Firestore for Document Storage

Use Firestore for structured agent data, conversation history, and RAG documents:

```python
from agentic_brain.storage import FirestoreStorage
from agentic_brain.rag import RAGPipeline

# Initialize Firestore storage
storage = FirestoreStorage(
    project_id="your-project",
    credentials_file="/path/to/credentials.json"
)

# Store conversation history
await storage.save_conversation(
    session_id="user-123",
    messages=[
        {"role": "user", "content": "What's the weather?"},
        {"role": "assistant", "content": "It's sunny and 72°F!"}
    ]
)

# Retrieve conversation
history = await storage.get_conversation("user-123")

# Use with RAG pipeline
rag = RAGPipeline(
    document_store=storage,
    collection="knowledge_base"
)
await rag.ingest(documents)
answer = await rag.query("What's our refund policy?")
```

### Firestore Collections Structure

```
firestore/
├── sessions/
│   └── {session_id}/
│       ├── messages/         # Chat history
│       ├── context/          # Session context
│       └── metadata/         # User preferences
├── agents/
│   └── {agent_id}/
│       ├── config/           # Agent configuration
│       └── tools/            # Available tools
├── knowledge_base/
│   └── {doc_id}/             # RAG documents
│       ├── content
│       ├── embedding
│       └── metadata
└── analytics/
    └── {date}/               # Usage metrics
```

---

## 🔐 Firebase Authentication Integration

Secure your agents with Firebase Auth:

```python
from agentic_brain.auth import FirebaseAuthProvider
from agentic_brain import Agent

# Initialize Firebase Auth
auth = FirebaseAuthProvider(
    project_id="your-project",
    credentials_file="/path/to/credentials.json"
)

# Verify user token (from client SDK)
user = await auth.verify_token(id_token)
print(f"Authenticated: {user.uid}, {user.email}")

# Create session scoped to user
agent = Agent(
    "personal-assistant",
    user_id=user.uid,
    scopes=["personal"]  # Data isolation
)

# Rate limiting per user
@auth.rate_limit(requests=100, window=3600)
async def chat(user_id: str, message: str):
    return await agent.chat(message)
```

### Supported Auth Providers

| Provider | Setup |
|----------|-------|
| **Email/Password** | Built-in, no config needed |
| **Google** | Add Google OAuth credentials |
| **Apple** | Add Apple Sign-In config |
| **Anonymous** | Great for demos, trials |
| **Custom Token** | Your own auth backend |
| **Phone** | SMS verification |

---

## 📱 Cross-Device Sync

Real-time sync between web, mobile, and desktop:

```python
# Same session ID = same conversation everywhere
SESSION_ID = f"user_{user.uid}_main"

# Python backend
transport = FirebaseTransport(config, session_id=SESSION_ID)

# JavaScript web client
# const ref = firebase.database().ref(`sessions/${SESSION_ID}/messages`);
# ref.on('child_added', (snapshot) => displayMessage(snapshot.val()));

# All clients see messages instantly!
```

### Client SDKs

```javascript
// Web/React
import { initializeApp } from 'firebase/app';
import { getDatabase, ref, push, onChildAdded } from 'firebase/database';

const app = initializeApp(firebaseConfig);
const db = getDatabase(app);

// Listen for messages
const messagesRef = ref(db, `sessions/${sessionId}/messages`);
onChildAdded(messagesRef, (snapshot) => {
    const message = snapshot.val();
    addMessageToUI(message);
});

// Send message
await push(messagesRef, {
    content: userInput,
    role: 'user',
    timestamp: Date.now()
});
```

```swift
// iOS/Swift
let ref = Database.database().reference()
    .child("sessions")
    .child(sessionId)
    .child("messages")

// Listen for new messages
ref.observe(.childAdded) { snapshot in
    if let message = snapshot.value as? [String: Any] {
        self.displayMessage(message)
    }
}
```

---

## 🔌 Offline Support

Messages queue locally when offline, sync automatically when reconnected:

```python
from agentic_brain.transport import FirebaseTransport, OfflineConfig

# Enable offline mode
transport = FirebaseTransport(
    config,
    session_id="user-123",
    offline=OfflineConfig(
        enabled=True,
        cache_size_mb=100,           # Local cache size
        sync_on_reconnect=True,      # Auto-sync when back online
        conflict_resolution="latest" # Newest message wins
    )
)

# Check connection state
if transport.is_offline:
    print("Working offline - messages will sync later")
    
# Register callbacks
transport.on_reconnect(lambda: print("Back online! Syncing..."))
transport.on_disconnect(lambda: print("Gone offline"))
```

### Offline Queue

```python
# View pending offline messages
pending = await transport.get_offline_queue()
print(f"{len(pending)} messages waiting to sync")

# Force sync (if online)
synced = await transport.force_sync()
print(f"Synced {synced} messages")
```

---

## ☁️ Cloud Functions Integration

Deploy serverless agent endpoints:

```python
# functions/main.py
from firebase_functions import https_fn
from agentic_brain import Agent

agent = Agent("cloud-assistant")

@https_fn.on_request()
def chat(req: https_fn.Request) -> https_fn.Response:
    """HTTP endpoint for agent chat."""
    data = req.get_json()
    response = agent.chat_sync(data["message"])
    return https_fn.Response({"response": response})

@https_fn.on_call()
def chat_secure(req: https_fn.CallableRequest):
    """Authenticated endpoint (requires Firebase Auth)."""
    user_id = req.auth.uid
    message = req.data["message"]
    
    # User-scoped agent
    user_agent = Agent(f"assistant-{user_id}")
    return {"response": user_agent.chat_sync(message)}
```

### Deploy

```bash
firebase deploy --only functions
```

---

## 📊 Analytics & Monitoring

Track agent usage with Firebase Analytics:

```python
from agentic_brain.analytics import FirebaseAnalytics

analytics = FirebaseAnalytics(config)

# Log events
await analytics.log_event("agent_response", {
    "session_id": session_id,
    "tokens_used": response.usage.total_tokens,
    "latency_ms": response.latency,
    "model": "gpt-4o"
})

# Track user properties
await analytics.set_user_property(user_id, "plan", "premium")
await analytics.set_user_property(user_id, "messages_sent", 150)
```

### Built-in Dashboards

- **Response times** - p50, p95, p99 latencies
- **Error rates** - Failed requests, retries
- **Usage patterns** - Peak hours, popular topics
- **Cost tracking** - Token usage, API costs

---

## 🏗️ Architecture Patterns

### Pattern 1: Simple Chat App

```
┌──────────┐    ┌──────────┐    ┌──────────┐
│  React   │◄──►│ Firebase │◄──►│  Python  │
│   App    │    │   RTDB   │    │  Agent   │
└──────────┘    └──────────┘    └──────────┘
```

### Pattern 2: Multi-Agent System

```
┌──────────────────────────────────────────────┐
│                  Firebase                     │
├──────────┬───────────┬───────────┬───────────┤
│   RTDB   │ Firestore │   Auth    │ Functions │
│ (chat)   │ (RAG/docs)│ (users)   │ (workers) │
└────┬─────┴─────┬─────┴─────┬─────┴─────┬─────┘
     │           │           │           │
     ▼           ▼           ▼           ▼
┌─────────┐ ┌─────────┐ ┌─────────┐ ┌─────────┐
│  Chat   │ │ Research│ │  Auth   │ │Analytics│
│  Agent  │ │  Agent  │ │ Service │ │ Agent   │
└─────────┘ └─────────┘ └─────────┘ └─────────┘
```

### Pattern 3: Enterprise with Neo4j

```
┌──────────┐    ┌──────────┐    ┌──────────┐    ┌──────────┐
│ Firebase │◄──►│  Agent   │◄──►│  Neo4j   │◄──►│  Vector  │
│   Auth   │    │  Brain   │    │ GraphRAG │    │  Search  │
└──────────┘    └──────────┘    └──────────┘    └──────────┘
      ▲               │
      │               ▼
┌─────┴────┐    ┌──────────┐
│ Firestore │◄──│  History │
│ (backup)  │   │  Store   │
└───────────┘   └──────────┘
```

---

## 💰 Cost Optimization

### Free Tier Limits (Generous!)

| Service | Free Tier | Enough For |
|---------|-----------|------------|
| Realtime DB | 1 GB storage, 10 GB/month transfer | ~50K daily users |
| Firestore | 1 GB storage, 50K reads/day | ~10K documents |
| Auth | Unlimited | Unlimited users |
| Functions | 2M invocations/month | ~70K/day |
| Hosting | 10 GB storage, 10 GB/month | Most apps |

### Best Practices

```python
# Batch writes to reduce costs
async with storage.batch() as batch:
    for msg in messages:
        batch.add(msg)
    # Single write operation!
    
# Use shallow queries
messages = await transport.get_messages(
    limit=50,           # Paginate
    shallow=True        # Exclude nested data
)

# Enable local caching
transport = FirebaseTransport(
    config,
    cache_ttl=300  # 5 min cache
)
```

---

## 🔧 Configuration Reference

### Full Configuration

```python
from agentic_brain.transport import FirebaseTransport, TransportConfig

config = TransportConfig(
    # Required
    firebase_url="https://project.firebaseio.com",
    firebase_credentials="/path/to/credentials.json",
    
    # Optional
    firebase_project_id="your-project",
    
    # Performance
    max_retries=3,
    retry_delay=1.0,
    connection_timeout=30,
    
    # Offline
    offline_enabled=True,
    offline_cache_mb=100,
    
    # Security
    enable_emulator=False,  # For local dev
    emulator_host="localhost:9000",
)
```

### Environment Variables

```bash
# Firebase config
FIREBASE_PROJECT_ID=your-project-id
FIREBASE_DATABASE_URL=https://your-project.firebaseio.com
FIREBASE_CREDENTIALS_FILE=/path/to/credentials.json

# Optional
FIREBASE_EMULATOR_HOST=localhost:9000
FIREBASE_STORAGE_BUCKET=your-project.appspot.com
```

---

## 🧪 Testing with Emulators

```bash
# Start Firebase emulators
firebase emulators:start --only database,firestore,auth
```

```python
# Connect to emulators
config = TransportConfig(
    firebase_url="http://localhost:9000",
    enable_emulator=True,
    emulator_host="localhost:9000"
)

# Tests run locally, no cloud costs!
```

---

## 🚀 Production Checklist

- [ ] **Security Rules** - Lock down RTDB and Firestore rules
- [ ] **Indexes** - Create Firestore indexes for queries
- [ ] **Backups** - Enable automated Firestore backups
- [ ] **Monitoring** - Set up Firebase Performance Monitoring
- [ ] **Rate Limits** - Implement per-user rate limiting
- [ ] **Error Handling** - Graceful offline/reconnect handling
- [ ] **Cost Alerts** - Set budget alerts in GCP

---

## 📚 Resources

- [Firebase Documentation](https://firebase.google.com/docs)
- [Realtime Database Guide](https://firebase.google.com/docs/database)
- [Firestore Guide](https://firebase.google.com/docs/firestore)
- [Firebase Admin Python SDK](https://firebase.google.com/docs/admin/setup)
- [Agentic Brain Examples](../../examples/)

---

## 🆚 Firebase vs Alternatives

| Feature | Firebase | Supabase | AWS Amplify |
|---------|----------|----------|-------------|
| **Realtime** | ✅ Native | ✅ Native | ⚠️ AppSync |
| **Offline** | ✅ Built-in | ⚠️ Manual | ⚠️ Manual |
| **Free Tier** | ✅ Generous | ✅ Good | ⚠️ Limited |
| **Scaling** | ✅ Auto | ✅ Auto | ✅ Auto |
| **Setup Time** | 5 min | 10 min | 30 min |
| **Python SDK** | ✅ Full | ⚠️ Basic | ⚠️ JS-focused |

**Firebase wins for:**
- Mobile-first applications
- Offline-first requirements
- Rapid prototyping
- Cross-platform sync

---

*Firebase + Agentic Brain = Real-time AI that works everywhere, even offline.*
