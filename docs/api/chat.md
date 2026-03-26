# Chat Module API

High-level chatbot with automatic session persistence and memory integration. Perfect for building conversational AI applications.

## Table of Contents
- [Chatbot](#chatbot) - Main chatbot class
- [ChatConfig](#chatconfig) - Configuration
- [Session](#session) - Session management
- [SessionManager](#sessionmanager) - Multi-session handling
- [ChatMessage](#chatmessage) - Message objects
- [Examples](#examples)

---

## Chatbot

The main class for building chatbots. Handles conversations, session persistence, and memory integration automatically.

### Signature

```python
class Chatbot:
    def __init__(
        self,
        name: str,
        memory: Optional[Any] = None,  # Neo4jMemory
        config: Optional[ChatConfig] = None,
        llm: Optional[Any] = None,  # LLMRouter or callable
        system_prompt: Optional[str] = None,
        on_message: Optional[Callable[[ChatMessage], None]] = None,
        on_response: Optional[Callable[[ChatMessage], None]] = None,
        on_error: Optional[Callable[[Exception], None]] = None,
    ) -> None:
        """Initialize chatbot."""
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | required | Bot name/identifier (e.g., "support", "assistant") |
| `memory` | `Neo4jMemory` | `None` | Memory backend for long-term storage. If provided, enables automatic context retrieval |
| `config` | `ChatConfig` | `None` | Configuration object. If None, uses defaults |
| `llm` | callable/Router | `None` | LLM provider. If None, attempts Ollama on localhost:11434 |
| `system_prompt` | `str` | `None` | Custom system prompt. Overrides config |
| `on_message` | callable | `None` | Lifecycle hook: called when user message received |
| `on_response` | callable | `None` | Lifecycle hook: called when bot response generated |
| `on_error` | callable | `None` | Lifecycle hook: called on errors |

### Methods

#### `chat()`

Send a message and get a response.

```python
def chat(
    self,
    message: str,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> str:
```

**Parameters:**
- `message` (str): User's message
- `session_id` (str, optional): Session identifier. Auto-generated if not provided
- `user_id` (str, optional): User/customer ID. Used for data isolation in business mode
- `metadata` (dict, optional): Additional data to store with message (tokens, source, etc.)

**Returns:**
- `str`: Bot's response text

**Raises:**
- Exceptions are caught and returned as error messages. Use `on_error` hook for detailed errors

**Example:**
```python
bot = Chatbot("support")

# Simple usage
response = bot.chat("What's your return policy?")
print(response)

# With session and user tracking
response = bot.chat(
    "Help me",
    session_id="chat_123",
    user_id="customer_456",
    metadata={"source": "web"}
)

# Multiple users (isolated in business mode)
bot = Chatbot("support", config=ChatConfig.business())
bot.chat("Help me", user_id="customer_a")  # Isolated
bot.chat("Help me", user_id="customer_b")  # Isolated
```

---

#### `get_session()`

Retrieve session information including history.

```python
def get_session(
    self,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> ChatSession:
```

**Parameters:**
- `session_id` (str, optional): Session to retrieve
- `user_id` (str, optional): User ID for default session

**Returns:**
- `ChatSession`: Session object with history

**Example:**
```python
bot = Chatbot("assistant")
session = bot.get_session(user_id="customer_123")

print(f"Messages: {session.message_count}")
print(f"Last message: {session.last_message.content}")

for msg in session.history:
    print(f"{msg.role}: {msg.content}")
```

---

#### `clear_session()`

Clear message history for a session.

```python
def clear_session(
    self,
    session_id: Optional[str] = None,
    user_id: Optional[str] = None
) -> None:
```

**Example:**
```python
bot = Chatbot("assistant")
bot.chat("Hello")
bot.clear_session(user_id="customer_123")
# Session history cleared, but session still exists
```

---

#### `set_system_prompt()`

Update the system prompt at runtime.

```python
def set_system_prompt(self, prompt: str) -> None:
```

**Example:**
```python
bot = Chatbot("assistant")
bot.set_system_prompt("You are a helpful Python expert. Be concise.")
```

---

#### `get_stats()`

Get usage statistics for monitoring and debugging.

```python
def get_stats(self) -> Dict[str, Any]:
```

**Returns:**
```python
{
    "messages_received": 42,
    "responses_sent": 42,
    "errors": 0,
    "sessions_created": 5,
    "name": "support",
    "model": "llama3.1:8b",
    "memory_enabled": True,
    "persistence_enabled": True
}
```

**Example:**
```python
bot = Chatbot("assistant")
# ... after some conversations ...
stats = bot.get_stats()
print(f"Processed {stats['messages_received']} messages")
print(f"Error rate: {stats['errors'] / stats['messages_received']:.1%}")
```

---

## ChatConfig

Configuration object for chatbots. All settings have sensible defaults.

### Signature

```python
@dataclass
class ChatConfig:
    max_history: int = 100
    persist_sessions: bool = True
    session_timeout: int = 3600
    session_dir: Path = ~/.agentic_brain/sessions
    use_memory: bool = True
    memory_threshold: float = 0.7
    model: str = "llama3.1:8b"
    temperature: float = 0.7
    max_tokens: int = 1024
    system_prompt: Optional[str] = None
    customer_isolation: bool = False
    hooks_file: Optional[Path] = None
```

### Parameters

| Parameter | Default | Description |
|-----------|---------|-------------|
| `max_history` | `100` | Maximum messages to keep in memory per session |
| `persist_sessions` | `True` | Save sessions to disk for recovery |
| `session_timeout` | `3600` (1 hour) | Session expiration time in seconds |
| `session_dir` | `~/.agentic_brain/sessions` | Directory for session files |
| `use_memory` | `True` | Store important facts in Neo4j |
| `memory_threshold` | `0.7` | Confidence threshold for storing (0-1) |
| `model` | `llama3.1:8b` | Default LLM model (Ollama format) |
| `temperature` | `0.7` | LLM temperature (0=deterministic, 1=creative) |
| `max_tokens` | `1024` | Max tokens in response |
| `system_prompt` | `None` | Custom system prompt (None = auto-generated) |
| `customer_isolation` | `False` | Enable per-customer data isolation |
| `hooks_file` | `None` | Path to hooks.json for lifecycle events |

### Class Methods

#### `minimal()`

Create minimal configuration (no persistence, no memory).

```python
config = ChatConfig.minimal()
# Use for testing or stateless deployments
```

#### `business()`

Create business configuration with isolation enabled.

```python
config = ChatConfig.business()
# Customer isolation: True
# Persistence: True  
# Timeout: 2 hours
```

#### `from_dict()`

Create config from dictionary.

```python
config = ChatConfig.from_dict({
    "max_history": 200,
    "temperature": 0.5
})
```

### Examples

```python
# Default config (production-ready)
bot = Chatbot("assistant")

# Custom config
config = ChatConfig(
    max_history=200,
    temperature=0.5,
    persist_sessions=True
)
bot = Chatbot("assistant", config=config)

# Minimal for testing
config = ChatConfig.minimal()
bot = Chatbot("test", config=config)

# Business mode with isolation
config = ChatConfig.business()
bot = Chatbot("support", config=config)
```

---

## Session

Represents a single chat session with history and metadata.

### Signature

```python
@dataclass
class Session:
    session_id: str
    user_id: Optional[str] = None
    bot_name: str = "assistant"
    messages: List[Dict[str, Any]] = []
    metadata: Dict[str, Any] = {}
    created_at: str  # ISO format
    updated_at: str  # ISO format
```

### Methods

#### `add_message()`

Add a message to session history.

```python
def add_message(
    self,
    role: str,
    content: str,
    **kwargs
) -> Dict[str, Any]:
```

**Parameters:**
- `role` ("user" | "assistant" | "system"): Message role
- `content` (str): Message text
- `**kwargs`: Additional metadata (tokens, latency, etc.)

**Returns:** Message dictionary with timestamp

**Example:**
```python
session = Session(session_id="chat_123")
session.add_message("user", "Hello!", source="web")
session.add_message("assistant", "Hi there!")
```

#### `get_history()`

Get message history, optionally limited.

```python
def get_history(self, limit: Optional[int] = None) -> List[Dict]:
```

**Example:**
```python
# Get last 10 messages
recent = session.get_history(limit=10)

# Get all messages
all_messages = session.get_history()
```

#### `clear_history()`

Clear all messages from session.

```python
def clear_history(self) -> None:
```

#### `to_dict()` / `from_dict()`

Serialize/deserialize sessions.

```python
# Save to JSON
data = session.to_dict()
json.dump(data, open("session.json", "w"))

# Load from JSON
data = json.load(open("session.json"))
session = Session.from_dict(data)
```

---

## SessionManager

Manages multiple sessions with automatic persistence and cleanup.

### Signature

```python
class SessionManager:
    def __init__(
        self,
        session_dir: Path,
        timeout_seconds: int = 3600,
        auto_cleanup: bool = True
    ) -> None:
```

### Methods

#### `get_session()`

Get or create a session.

```python
def get_session(
    self,
    session_id: str,
    user_id: Optional[str] = None,
    bot_name: str = "assistant"
) -> Session:
```

**Example:**
```python
manager = SessionManager(Path("./sessions"))
session = manager.get_session("user_123", user_id="123")
session.add_message("user", "Hello")
```

#### `save_session()`

Persist session to disk.

```python
def save_session(self, session: Session) -> bool:
```

#### `load_session()`

Load session from disk.

```python
def load_session(self, session_id: str) -> Optional[Session]:
```

#### `delete_session()`

Delete session from memory and disk.

```python
def delete_session(self, session_id: str) -> bool:
```

#### `list_sessions()`

List all active sessions.

```python
def list_sessions(self) -> List[str]:
```

#### `get_session_count()`

Get count of active sessions.

```python
def get_session_count(self) -> int:
```

---

## ChatMessage

Individual message in a conversation.

### Signature

```python
@dataclass
class ChatMessage:
    role: str  # "user", "assistant", "system"
    content: str
    timestamp: str = ISO format datetime
    metadata: Dict[str, Any] = {}
```

### Methods

#### `to_dict()` / `from_dict()`

```python
msg = ChatMessage(role="user", content="Hello")
data = msg.to_dict()

msg2 = ChatMessage.from_dict(data)
```

---

## ChatSession

Read-only view of session data (returned by `get_session()`).

### Signature

```python
@dataclass
class ChatSession:
    session_id: str
    user_id: Optional[str]
    history: List[ChatMessage]
```

### Properties

- `message_count` - Number of messages
- `last_message` - Last message or None

---

## Examples

### Example 1: Simple Chatbot

```python
from agentic_brain import Chatbot

# Create bot
bot = Chatbot("assistant")

# Chat
response = bot.chat("What's 2 + 2?")
print(response)  # -> "2 + 2 equals 4."
```

### Example 2: Customer Support with Isolation

```python
from agentic_brain import Chatbot, ChatConfig

# Create bot with customer isolation
config = ChatConfig.business()
bot = Chatbot("support", config=config)

# Each customer is isolated
bot.chat("I want to return my order", user_id="customer_a")
bot.chat("I want to return my order", user_id="customer_b")

# Data is separate - no cross-contamination
```

### Example 3: With Memory

```python
from agentic_brain import Chatbot, Neo4jMemory

# Create with memory
memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)
bot = Chatbot("assistant", memory=memory)

# Store facts automatically
bot.chat("My name is Alice and I work at Acme Corp")

# Retrieved automatically in future conversations
response = bot.chat("What company do I work for?")
# -> "You work at Acme Corp."
```

### Example 4: With Hooks

```python
from agentic_brain import Chatbot

def on_user_message(msg):
    print(f"📨 User: {msg.content}")

def on_bot_response(msg):
    print(f"🤖 Bot: {msg.content}")

def on_error(error):
    print(f"❌ Error: {error}")

bot = Chatbot(
    "assistant",
    on_message=on_user_message,
    on_response=on_bot_response,
    on_error=on_error
)

# Now all messages and errors are logged
response = bot.chat("Hello!")
```

### Example 5: Session Management

```python
from agentic_brain import Chatbot

bot = Chatbot("assistant")

# Multi-turn conversation (same session)
session_id = "chat_123"
bot.chat("My name is Bob", session_id=session_id)
bot.chat("What's my name?", session_id=session_id)  # -> "Your name is Bob"

# Check session history
session = bot.get_session(session_id=session_id)
print(f"Message count: {session.message_count}")

for msg in session.history:
    print(f"{msg.role.upper()}: {msg.content}")

# Clear history
bot.clear_session(session_id=session_id)
```

### Example 6: Custom Configuration

```python
from agentic_brain import Chatbot, ChatConfig

# Custom config
config = ChatConfig(
    max_history=50,
    temperature=0.3,  # More deterministic
    model="ollama:mistral-nemo",
    persist_sessions=False,  # Development mode
)

bot = Chatbot("dev-assistant", config=config)
response = bot.chat("Hello!")
```

---

## See Also

- [Memory Module](./memory.md) - Long-term storage
- [RAG Module](./rag.md) - Question-answering
- [Agent Module](./agent.md) - Full-featured agent
- [Hooks Module](./hooks.md) - Lifecycle events
- [Index](./index.md) - All modules

---

**Last Updated**: 2026-03-20  
**Status**: Production Ready ✅
