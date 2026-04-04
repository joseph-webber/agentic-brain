# Agentic Brain Chat Module

Add a production-ready chatbot to your application in minutes. The chat module provides session persistence, Neo4j memory integration, and multi-user support.

**Key Features:**
- 🚀 Quick Start: 3 lines of code to get chatting
- 💾 Session Persistence: Survives app restarts
- 🧠 Memory Integration: Long-term knowledge with Neo4j
- 👥 Multi-User Isolation: Perfect for B2B/SaaS
- 🔗 Lifecycle Hooks: Respond to chat events
- 🤖 Any LLM: Works with Ollama, OpenAI, Anthropic, etc.

---

## Quick Start

Get your first chatbot running in 3 lines:

```python
from agentic_brain.chat import Chatbot

bot = Chatbot("assistant")
response = bot.chat("Hello! What's your name?")
print(response)  # Output from local LLM
```

That's it! The chatbot uses:
- **Default LLM**: Ollama at `http://localhost:11434` (llama3.1:8b)
- **Default Storage**: `~/.agentic_brain/sessions/` (auto-created)
- **Default Config**: Sensible production-ready settings

### Next Steps

Want more? Add memory, configure behavior, or enable multi-user support:

```python
# Add long-term memory
from agentic_brain import Neo4jMemory
memory = Neo4jMemory()
bot = Chatbot("support", memory=memory)

# Multi-user support
bot.chat("Help me with order 123", user_id="customer_456")
bot.chat("Help me with order 789", user_id="customer_789")  # Isolated

# Custom hooks
def log_response(msg):
    print(f"Bot said: {msg.content}")

bot = Chatbot("assistant", on_response=log_response)
```

---

## Configuration

### Quickest Config: Presets

Three ready-to-use configurations:

```python
from agentic_brain.chat import Chatbot, ChatConfig

# Default production config
config = ChatConfig()
bot = Chatbot("assistant", config=config)

# Minimal - no persistence, no memory (good for testing)
config = ChatConfig.minimal()
bot = Chatbot("assistant", config=config)

# Business - customer isolation enabled
config = ChatConfig.business()
bot = Chatbot("support", config=config)
```

### Full Configuration Options

```python
from agentic_brain.chat import ChatConfig
from pathlib import Path

config = ChatConfig(
    # Session settings
    max_history=100,              # Keep last N messages in memory
    persist_sessions=True,        # Save to disk for recovery
    session_timeout=3600,         # 1 hour before session expires
    session_dir=Path("./sessions"),  # Where to store session files
    
    # Memory settings
    use_memory=True,              # Store facts in Neo4j
    memory_threshold=0.7,         # Confidence for storing (0-1)
    
    # LLM settings
    model="llama3.1:8b",         # Ollama model to use
    temperature=0.7,             # 0=deterministic, 1=creative
    max_tokens=1024,             # Max response length
    system_prompt=None,          # Custom system prompt (None = default)
    
    # Business settings
    customer_isolation=False,    # Enable per-user data isolation
    
    # Hooks
    hooks_file=None,             # Path to hooks.json
)

bot = Chatbot("support", config=config)
```

### Configuration by Use Case

**Support Chatbot (B2B)**
```python
config = ChatConfig(
    customer_isolation=True,     # Each customer isolated
    max_history=200,             # Longer context
    persist_sessions=True,
    model="llama3.1:70b",        # Larger model for quality
    temperature=0.5,             # More deterministic
)
bot = Chatbot("support", config=config, memory=memory)
```

**Lightweight Chatbot (Testing)**
```python
config = ChatConfig.minimal()
# No persistence, no memory, limited history
bot = Chatbot("test_bot", config=config)
```

**General Purpose Assistant**
```python
config = ChatConfig(
    max_history=50,
    temperature=0.7,
    use_memory=True,
)
bot = Chatbot("assistant", config=config, memory=memory)
```

**Multi-Tenant SaaS**
```python
config = ChatConfig.business()
bot = Chatbot("app_assistant", config=config, memory=memory)

# Isolate each tenant's data
bot.chat("Help me", user_id=f"tenant_{tenant_id}")
```

---

## Session Persistence

Sessions automatically save after each message, so your chatbot recovers if the app restarts.

### How It Works

```python
from agentic_brain.chat import Chatbot

bot = Chatbot("support")

# First run
bot.chat("Remember my name: Alice")  # Saved to ~/.agentic_brain/sessions/
bot.chat("What's my name?")          # "Your name is Alice"

# App restarts...
bot = Chatbot("support")  # New instance, same session dir

# Session recovered from disk
response = bot.chat("What's my name?")  # Still knows it's "Alice"!
```

### Session Files

Sessions are stored as JSON files in `session_dir`:

```
~/.agentic_brain/sessions/
├── session_abc123def456.json
├── session_xyz789qrs234.json
└── ...
```

Each file contains:
```json
{
  "session_id": "user_alice",
  "user_id": "alice_123",
  "bot_name": "support",
  "messages": [
    {
      "role": "user",
      "content": "Remember my name: Alice",
      "timestamp": "2024-03-19T15:30:00.123456"
    },
    {
      "role": "assistant",
      "content": "Got it, your name is Alice.",
      "timestamp": "2024-03-19T15:30:01.654321"
    }
  ],
  "created_at": "2024-03-19T15:30:00.123456",
  "updated_at": "2024-03-19T15:30:01.654321"
}
```

### Managing Sessions

```python
from agentic_brain.chat import Chatbot

bot = Chatbot("support")

# Get session info
session = bot.get_session(session_id="user_alice")
print(f"Messages: {session.message_count}")
print(f"Last message: {session.last_message.content}")

# Clear session history
bot.clear_session(user_id="alice_123")

# Check all active sessions
config = bot.config
manager = bot.session_manager
print(f"Active sessions: {manager.get_session_count()}")
print(f"All sessions: {manager.list_sessions()}")
```

### Disabling Persistence

For development or testing, disable persistence:

```python
config = ChatConfig(persist_sessions=False)
bot = Chatbot("test_bot", config=config)

# Sessions stay in memory only, lost on restart
```

---

## Memory Integration

Combine sessions with Neo4j memory for long-term knowledge that survives even if sessions expire.

### Basic Memory Usage

```python
from agentic_brain import Neo4jMemory
from agentic_brain.chat import Chatbot

# Connect to Neo4j
memory = Neo4jMemory()

# Create chatbot with memory
bot = Chatbot("support", memory=memory)

# Bot automatically stores and retrieves facts
bot.chat("My account number is ACC-12345")
bot.chat("I prefer email notifications")
bot.chat("I'm based in New York")

# Later (even after session expires)...
response = bot.chat("What's my account number?")
# Bot retrieves from memory: "Your account number is ACC-12345"
```

### How Memory Works

The chatbot automatically:

1. **Stores** important facts when it detects patterns like:
   - "My name is..."
   - "I work at..."
   - "My email is..."
   - "Remember that..."
   - And similar statements

2. **Retrieves** relevant context before generating responses:
   ```python
   # Chatbot internally does:
   context = memory.search("What's my account?")
   # Found: "Your account number is ACC-12345"
   # Uses this context in the response
   ```

### Memory + Sessions Combined

- **Session history** (last ~100 messages): Fast, specific to this conversation
- **Long-term memory** (Neo4j): Persistent facts across sessions

```python
# Session: User asked about billing last week
# Memory: User's account, contact info, preferences
# Together: Full context for great customer support

bot.chat("Help me understand my bill")
# Uses both session history AND long-term memory
```

### Disabling Memory

```python
config = ChatConfig(use_memory=False)
bot = Chatbot("assistant", config=config)
```

---

## Multi-User / Customer Isolation

For B2B apps, SaaS platforms, or any multi-tenant system: isolate data per user/customer.

### Basic Multi-User

```python
from agentic_brain.chat import Chatbot, ChatConfig

config = ChatConfig.business()  # Enables customer_isolation
bot = Chatbot("support", config=config)

# Customer 1
bot.chat("I need a refund", user_id="cust_001")
response = bot.chat("What was my issue?", user_id="cust_001")
# Bot knows: refund request

# Customer 2 (completely isolated)
bot.chat("I need a refund", user_id="cust_002")
response = bot.chat("What was my issue?", user_id="cust_002")
# Bot knows: refund request (but different conversation)

# Cross-customer isolation verified
bot.chat("What do I need?", user_id="cust_001")
# Bot says: refund (not confused by cust_002)
```

### How Isolation Works

1. **Session isolation**: Each `user_id` gets its own session file
   - Customer 1 session: `~/.agentic_brain/sessions/session_hash(user_cust_001).json`
   - Customer 2 session: `~/.agentic_brain/sessions/session_hash(user_cust_002).json`

2. **Memory isolation**: When `customer_isolation=True`:
   ```python
   # Chatbot only retrieves memory for current user
   context = memory.search(query, user_id=user_id)  # Filtered!
   ```

3. **Multi-tenant ready**:
   ```python
   # In your FastAPI/Flask endpoint
   @app.post("/chat")
   def chat_endpoint(message: str, user_id: str):
       bot = Chatbot("support")
       response = bot.chat(message, user_id=user_id)
       return {"response": response}
   
   # Each user_id is isolated automatically
   ```

### SaaS Example

```python
from fastapi import FastAPI
from agentic_brain.chat import Chatbot, ChatConfig
from agentic_brain import Neo4jMemory

app = FastAPI()
memory = Neo4jMemory()
config = ChatConfig.business()
bot = Chatbot("support", config=config, memory=memory)

@app.post("/api/chat")
def chat(tenant_id: str, user_id: str, message: str):
    # Combine tenant + user for full isolation
    combined_user_id = f"{tenant_id}:{user_id}"
    
    response = bot.chat(
        message=message,
        user_id=combined_user_id
    )
    
    return {"response": response}

# /api/chat?tenant_id=acme&user_id=alice -> Isolated
# /api/chat?tenant_id=acme&user_id=bob   -> Different conversation
# /api/chat?tenant_id=bigco&user_id=alice -> Different tenant
```

---

## Lifecycle Hooks

Respond to chat events with custom logic: logging, monitoring, webhooks, etc.

### Available Hooks

```python
def on_user_message(msg: ChatMessage):
    """Called when user sends a message."""
    print(f"User: {msg.content}")
    # Examples: log message, increment counter, send to analytics

def on_bot_response(msg: ChatMessage):
    """Called when bot sends a response."""
    print(f"Bot: {msg.content}")
    # Examples: save to database, send to monitoring, trigger actions

def on_error(error: Exception):
    """Called when an error occurs."""
    print(f"Error: {error}")
    # Examples: alert ops team, trigger fallback, notify user

bot = Chatbot(
    "support",
    on_message=on_user_message,
    on_response=on_bot_response,
    on_error=on_error
)
```

### Practical Examples

**Logging to Analytics**
```python
def on_response(msg):
    analytics.log_event(
        event="chat_response",
        duration_ms=msg.metadata.get("duration_ms"),
        tokens=msg.metadata.get("tokens"),
    )

bot = Chatbot("support", on_response=on_response)
```

**Sending to Webhook**
```python
import requests

def on_message(msg):
    # Send to external system
    requests.post(
        "https://api.example.com/chat_log",
        json={
            "role": msg.role,
            "content": msg.content,
            "timestamp": msg.timestamp,
        }
    )

bot = Chatbot("support", on_message=on_message)
```

**Monitoring for Issues**
```python
def on_error(error):
    # Alert ops if critical error
    if isinstance(error, ConnectionError):
        send_alert_to_slack(f"Chat module connection error: {error}")
    else:
        log_error(error)

bot = Chatbot("support", on_error=on_error)
```

**Complex Hook with Multiple Actions**
```python
class ChatMonitor:
    def __init__(self):
        self.message_count = 0
        self.error_count = 0
    
    def on_message(self, msg):
        self.message_count += 1
        if self.message_count % 100 == 0:
            print(f"Messages: {self.message_count}")
    
    def on_error(self, error):
        self.error_count += 1
        if self.error_count > 10:
            raise RuntimeError("Too many errors, giving up")

monitor = ChatMonitor()
bot = Chatbot(
    "support",
    on_message=monitor.on_message,
    on_error=monitor.on_error
)
```

### Message Object

Hooks receive `ChatMessage` objects:

```python
@dataclass
class ChatMessage:
    role: str                           # "user" or "assistant"
    content: str                        # The message text
    timestamp: str                      # ISO format timestamp
    metadata: Dict[str, Any]            # Additional data
    # - tokens: Token count
    # - model: LLM model name
    # - duration_ms: Response time
```

---

## Best Practices

### 1. Always Use Persistence in Production

```python
# ✅ Good
config = ChatConfig(persist_sessions=True)
bot = Chatbot("support", config=config)

# ❌ Bad (testing only)
config = ChatConfig(persist_sessions=False)
bot = Chatbot("support", config=config)
```

### 2. Enable Memory for Better Responses

```python
# ✅ Good - remembers facts across sessions
memory = Neo4jMemory()
bot = Chatbot("support", memory=memory)

# ❌ Bad - no long-term memory
bot = Chatbot("support")  # Memory disabled by default in some modes
```

### 3. Use Sensible Session Timeouts

```python
# ✅ Good - balance between retention and cleanup
config = ChatConfig(
    session_timeout=3600,  # 1 hour - reasonable for most apps
)

# ❌ Bad - too short, loses context
config = ChatConfig(session_timeout=60)  # 1 minute - loses history

# ⚠️ Be careful - too long uses disk space
config = ChatConfig(session_timeout=86400*30)  # 30 days - storage heavy
```

### 4. Set Appropriate Temperature

```python
# ✅ For customer support (consistent, factual)
config = ChatConfig(temperature=0.5)  # More deterministic

# ✅ For creative assistant (engaging, varied)
config = ChatConfig(temperature=0.9)  # More creative

# ❌ Avoid extremes
config = ChatConfig(temperature=0.0)   # Always same response
config = ChatConfig(temperature=2.0)   # Random gibberish
```

### 5. Isolate Multi-User Data

```python
# ✅ Always provide user_id in multi-user apps
bot.chat("Help", user_id="user_123")

# ❌ Don't mix users without isolation
bot.chat("Help from user 1")
bot.chat("Help from user 2")  # May leak user 1's context
```

### 6. Handle Errors Gracefully

```python
# ✅ Good - catches and logs errors
try:
    response = bot.chat("Help")
except Exception as e:
    logger.error(f"Chat failed: {e}")
    return "Sorry, I'm having trouble. Please try again."

# ❌ Bad - crashes the whole app
response = bot.chat("Help")  # May raise exception
```

### 7. Monitor Resources

```python
# Check stats periodically
stats = bot.get_stats()
print(f"Messages: {stats['messages_received']}")
print(f"Errors: {stats['errors']}")
print(f"Sessions: {len(bot.session_manager.list_sessions())}")

# Alert if growing too fast
if stats['errors'] > 100:
    send_alert("Chat module error rate too high")
```

### 8. Version Your System Prompt

```python
# ✅ Good - can debug and roll back
SYSTEM_PROMPT_V2 = """You are a helpful support agent.
...instructions...
Version: 2.0
"""

bot = Chatbot("support", system_prompt=SYSTEM_PROMPT_V2)

# Later, if needed
SYSTEM_PROMPT_V3 = """..."""
bot.set_system_prompt(SYSTEM_PROMPT_V3)

# ❌ Bad - can't track what changed
bot = Chatbot("support", system_prompt="Be helpful")
```

---

## Troubleshooting

### Issue: "I'm currently unable to process your request"

**Cause**: LLM not responding. Default behavior falls back to this message.

**Solutions**:
```python
# 1. Check if Ollama is running
# $ ollama serve
# or specify custom LLM
def my_llm(messages):
    return "Custom response"

bot = Chatbot("support", llm=my_llm)

# 2. Check Ollama connection
import requests
try:
    response = requests.post("http://localhost:11434/api/chat", json={...})
except ConnectionError:
    print("Ollama not running on port 11434")

# 3. Verify model exists
# $ ollama list
# Pull if needed
# $ ollama pull llama3.1:8b
```

### Issue: Session Files Filling Disk

**Cause**: Sessions not being cleaned up (timeout not working).

**Solutions**:
```python
# 1. Enable auto-cleanup
config = ChatConfig(
    session_timeout=3600,  # Clean up after 1 hour
)
bot = Chatbot("support", config=config)

# 2. Manually clean old sessions
manager = bot.session_manager
manager._cleanup_expired()

# 3. Check disk usage
import os
size = sum(
    os.path.getsize(f) 
    for f in manager.session_dir.glob("**/*")
)
print(f"Sessions using {size / 1024 / 1024:.1f} MB")
```

### Issue: "Failed to store memory" or "Failed to retrieve context"

**Cause**: Neo4j not connected or memory not initialized.

**Solutions**:
```python
# 1. Check Neo4j connection
from agentic_brain import Neo4jMemory
try:
    memory = Neo4jMemory()
    # If this fails, Neo4j is not running
except Exception as e:
    print(f"Neo4j error: {e}")

# 2. Start Neo4j
# Via Docker: docker run -d -p 7474:7474 -p 7687:7687 neo4j
# Or local: brew services start neo4j

# 3. Disable memory if not needed
config = ChatConfig(use_memory=False)
bot = Chatbot("support", config=config)
```

### Issue: Different Users Seeing Each Other's Messages

**Cause**: Customer isolation not enabled.

**Solutions**:
```python
# 1. Enable customer_isolation in config
config = ChatConfig.business()  # Automatically enables isolation
bot = Chatbot("support", config=config)

# 2. Always provide user_id
bot.chat("Help", user_id="user_123")  # Good
bot.chat("Help")  # Bad - may use default session

# 3. Verify isolation working
session1 = bot.get_session(user_id="user_1")
session2 = bot.get_session(user_id="user_2")
assert len(session1.history) != len(session2.history)  # Different histories
```

### Issue: Chatbot Forgets Things Between Restarts

**Cause**: Sessions expired or persistence disabled.

**Solutions**:
```python
# 1. Check persistence enabled
config = ChatConfig(persist_sessions=True)  # Default
bot = Chatbot("support", config=config)

# 2. Check session timeout not too short
config = ChatConfig(session_timeout=3600)  # Not 60 seconds

# 3. Enable memory for long-term recall
memory = Neo4jMemory()
bot = Chatbot("support", memory=memory)  # Survives all restarts

# 4. Check session directory
config = bot.config
print(f"Sessions saved to: {config.session_dir}")
print(f"Session files: {list(config.session_dir.glob('*.json'))}")
```

### Issue: Slow Responses

**Cause**: Large history, large model, or network issues.

**Solutions**:
```python
# 1. Reduce history size
config = ChatConfig(max_history=20)  # Was 100
bot = Chatbot("support", config=config)

# 2. Use smaller model
config = ChatConfig(model="llama2:7b")  # Smaller than llama3.1:8b
bot = Chatbot("support", config=config)

# 3. Check network latency
import time
messages = [{"role": "user", "content": "Hi"}]
start = time.time()
response = bot._call_llm(messages)
elapsed = time.time() - start
print(f"Response time: {elapsed:.1f}s")

# 4. Disable memory queries if slow
config = ChatConfig(use_memory=False)
```

### Issue: Memory Not Storing Facts

**Cause**: Content doesn't match detection patterns.

**Solutions**:
```python
# Current detection patterns:
PATTERNS = [
    "remember", "my name is", "i am", "i work at",
    "my email", "my phone", "my address",
    "i like", "i prefer", "i need"
]

# Messages matching these are stored automatically
bot.chat("Remember my order is 12345")  # Stored (has "remember")
bot.chat("My email is alice@example.com")  # Stored (has "my email")
bot.chat("I prefer fast shipping")  # Stored (has "i prefer")

# If not working, enable debug logging
import logging
logging.basicConfig(level=logging.DEBUG)
# Look for "Stored memory:" messages
```

---

## API Reference

### Chatbot

```python
bot = Chatbot(
    name: str,
    memory: Optional[Neo4jMemory] = None,
    config: Optional[ChatConfig] = None,
    llm: Optional[Callable] = None,
    system_prompt: Optional[str] = None,
    on_message: Optional[Callable] = None,
    on_response: Optional[Callable] = None,
    on_error: Optional[Callable] = None,
)

# Methods
response: str = bot.chat(message, session_id=None, user_id=None, metadata=None)
session: ChatSession = bot.get_session(session_id=None, user_id=None)
bot.clear_session(session_id=None, user_id=None)
bot.set_system_prompt(prompt: str)
stats: Dict = bot.get_stats()
```

### ChatConfig

```python
config = ChatConfig(
    max_history=100,
    persist_sessions=True,
    session_timeout=3600,
    session_dir=Path.home() / ".agentic_brain" / "sessions",
    use_memory=True,
    memory_threshold=0.7,
    model="llama3.1:8b",
    temperature=0.7,
    max_tokens=1024,
    system_prompt=None,
    customer_isolation=False,
    hooks_file=None,
)

# Factory methods
ChatConfig.minimal()   # No persistence, no memory
ChatConfig.business()  # Customer isolation enabled
```

### Session

```python
session = bot.get_session(user_id="user_123")

# Properties
session.session_id: str
session.user_id: Optional[str]
session.history: List[ChatMessage]
session.message_count: int
session.last_message: Optional[ChatMessage]
```

### ChatMessage

```python
# From hooks or bot.get_session()
message.role: str               # "user" or "assistant"
message.content: str            # The message text
message.timestamp: str          # ISO format
message.metadata: Dict[str, Any]
```

---

## Examples

### Example 1: Simple Support Bot

```python
from agentic_brain.chat import Chatbot
from agentic_brain import Neo4jMemory

# Setup
memory = Neo4jMemory()
bot = Chatbot("support", memory=memory)

# Conversation
bot.chat("Hi, I need help with my order", user_id="cust_001")
bot.chat("My order number is 54321", user_id="cust_001")
bot.chat("When will it arrive?", user_id="cust_001")

# Bot uses context from:
# - This conversation (session)
# - User facts (memory)
# - System prompt
```

### Example 2: SaaS Integration

```python
from fastapi import FastAPI
from agentic_brain.chat import Chatbot, ChatConfig
from agentic_brain import Neo4jMemory

app = FastAPI()

config = ChatConfig.business()
memory = Neo4jMemory()
bot = Chatbot("assistant", config=config, memory=memory)

@app.post("/api/chat")
def chat_endpoint(tenant_id: str, user_id: str, message: str):
    # Combine tenant and user for full isolation
    isolated_user_id = f"{tenant_id}#{user_id}"
    
    response = bot.chat(
        message=message,
        user_id=isolated_user_id,
        metadata={"tenant_id": tenant_id}
    )
    
    return {"response": response}
```

### Example 3: Monitoring with Hooks

```python
import logging
from datetime import datetime
from agentic_brain.chat import Chatbot

logger = logging.getLogger(__name__)

def on_message(msg):
    logger.info(f"[{datetime.now().isoformat()}] User: {msg.content[:100]}")

def on_response(msg):
    logger.info(f"[{datetime.now().isoformat()}] Bot: {msg.content[:100]}")

def on_error(error):
    logger.error(f"Chat error: {error}")

bot = Chatbot(
    "support",
    on_message=on_message,
    on_response=on_response,
    on_error=on_error
)

# Now all messages are logged automatically
response = bot.chat("Help me")
```

### Example 4: Custom LLM Integration

```python
from agentic_brain.chat import Chatbot
import openai

def openai_llm(messages):
    """Use OpenAI instead of Ollama."""
    response = openai.ChatCompletion.create(
        model="gpt-4",
        messages=messages,
        temperature=0.7,
    )
    return response.choices[0].message.content

bot = Chatbot(
    "assistant",
    llm=openai_llm,  # Custom LLM
    system_prompt="You are a helpful assistant powered by GPT-4"
)

response = bot.chat("What's the capital of France?")
```

### Example 5: Development vs Production

```python
import os
from agentic_brain.chat import Chatbot, ChatConfig

if os.getenv("ENV") == "production":
    # Production: full features
    config = ChatConfig.business()
    from agentic_brain import Neo4jMemory
    memory = Neo4jMemory()
    bot = Chatbot("support", config=config, memory=memory)
else:
    # Development: minimal
    config = ChatConfig.minimal()
    bot = Chatbot("support", config=config)

response = bot.chat("Help")
```

---

## FAQ

**Q: Will the chatbot work without Ollama?**
A: Yes! Provide your own LLM via the `llm` parameter. Works with OpenAI, Anthropic, or any callable that takes messages and returns a response.

**Q: How long does a session last?**
A: By default, 1 hour (configurable via `session_timeout`). After that, it's cleaned up from disk but can be recovered from long-term memory if available.

**Q: Can I use this for a web app?**
A: Absolutely! Each HTTP request provides a `user_id`, and the chatbot handles isolation automatically.

**Q: What if I don't need Neo4j memory?**
A: Set `use_memory=False` in config. Sessions alone will remember the conversation.

**Q: How do I export chat history?**
A: Sessions are JSON files in `~/.agentic_brain/sessions/`. Parse them for export/analysis.

**Q: Can I change the system prompt later?**
A: Yes! Use `bot.set_system_prompt(new_prompt)`. Great for A/B testing.

**Q: What's the maximum conversation length?**
A: Limited by `max_history` (default 100 messages). Older messages are dropped.

**Q: Is this production-ready?**
A: Yes. Built with error handling, persistence, and monitoring in mind.

---

## See Also

- [Main Documentation](./INDEX.md)
- [Setup Guide](./SETUP.md)
- [Neo4j Memory Integration](./memory.md)
- [LLM Configuration](./LLM_GUIDE.md)
