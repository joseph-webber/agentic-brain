# Hooks Module API

Lifecycle event system for extensibility. Register handlers for key events throughout the agentic-brain lifecycle.

## Table of Contents
- [HooksManager](#hooksmanager) - Main hooks class
- [HookContext](#hookcontext) - Event context
- [Hook Events](#hook-events) - Available events
- [Examples](#examples)

---

## HooksManager

Manages lifecycle hooks for agentic-brain.

### Signature

```python
class HooksManager:
    def __init__(self, config_path: Optional[Path] = None) -> None:
        """Initialize hooks manager."""
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `config_path` | `Path` | `hooks.json` | Path to hooks configuration file |

### Built-in Hook Events

```python
HooksManager.ON_SESSION_START   # Session begins
HooksManager.ON_SESSION_END     # Session ends
HooksManager.ON_MESSAGE         # Message received
HooksManager.ON_RESPONSE        # Response generated
HooksManager.ON_ERROR           # Error occurred
```

### Methods

#### `register()`

Register a handler for a hook event.

```python
def register(
    self,
    event_type: str,
    handler: Callable[[HookContext], None]
) -> None:
```

**Parameters:**
- `event_type` (str): Hook event name
- `handler` (callable): Function that accepts HookContext

**Raises:**
- `ValueError`: If handler is not callable

**Example:**
```python
from agentic_brain.hooks import HooksManager

manager = HooksManager()

def on_message_received(context):
    print(f"Got message: {context.data['content']}")
    print(f"Timestamp: {context.timestamp}")

manager.register("on_message", on_message_received)
```

---

#### `unregister()`

Unregister a handler.

```python
def unregister(
    self,
    event_type: str,
    handler: Callable[[HookContext], None]
) -> bool:
```

**Returns:**
- `bool`: True if handler was removed, False if not found

**Example:**
```python
manager = HooksManager()

def my_handler(context):
    pass

manager.register("on_message", my_handler)
manager.unregister("on_message", my_handler)  # -> True
manager.unregister("on_message", my_handler)  # -> False
```

---

#### `fire()`

Fire a hook event to all registered handlers.

```python
def fire(
    self,
    event_type: str,
    data: Dict[str, Any]
) -> None:
```

**Parameters:**
- `event_type` (str): Event name
- `data` (dict): Event data to pass to handlers

**Example:**
```python
manager = HooksManager()

manager.register("on_message", lambda ctx: print(f"Got: {ctx.data}"))

# Fire the event
manager.fire("on_message", {"content": "Hello", "user_id": "123"})
# Output: Got: {'content': 'Hello', 'user_id': '123'}
```

---

#### `get_handlers()`

Get all handlers for an event.

```python
def get_handlers(self, event_type: str) -> List[Callable]:
```

**Returns:**
- List of handler functions

**Example:**
```python
manager = HooksManager()

manager.register("on_message", lambda ctx: print("Handler 1"))
manager.register("on_message", lambda ctx: print("Handler 2"))

handlers = manager.get_handlers("on_message")
print(f"Registered {len(handlers)} handlers")  # -> 2
```

---

#### `clear_handlers()`

Remove all handlers for an event.

```python
def clear_handlers(self, event_type: str) -> None:
```

**Example:**
```python
manager = HooksManager()
manager.register("on_message", lambda ctx: print("Handler"))
manager.clear_handlers("on_message")
```

---

## HookContext

Context data passed to hook handlers.

### Signature

```python
@dataclass
class HookContext:
    event_type: str
    timestamp: datetime
    data: Dict[str, Any]
```

### Methods

#### `to_dict()`

Serialize context to dictionary.

```python
def to_dict(self) -> Dict[str, Any]:
```

**Returns:**
```python
{
    "event_type": "on_message",
    "timestamp": "2026-03-20T12:34:56.789Z",
    "data": {...}
}
```

---

## Hook Events

### Built-in Events

#### `on_session_start`

Fired when a session begins.

**Context Data:**
```python
{
    "session_id": "session_123",
    "user_id": "user_456",
    "bot_name": "support"
}
```

**Example:**
```python
def on_session_start(context):
    print(f"Session started: {context.data['session_id']}")

manager.register("on_session_start", on_session_start)
```

---

#### `on_session_end`

Fired when a session ends.

**Context Data:**
```python
{
    "session_id": "session_123",
    "user_id": "user_456",
    "message_count": 42,
    "duration_seconds": 300
}
```

---

#### `on_message`

Fired when a user message is received.

**Context Data:**
```python
{
    "content": "Hello!",
    "role": "user",
    "session_id": "session_123",
    "user_id": "user_456"
}
```

---

#### `on_response`

Fired when a bot response is generated.

**Context Data:**
```python
{
    "content": "Hi there!",
    "role": "assistant",
    "session_id": "session_123",
    "model": "llama3.1:8b",
    "generation_time_ms": 245
}
```

---

#### `on_error`

Fired when an error occurs.

**Context Data:**
```python
{
    "error": "Connection timeout",
    "error_type": "ConnectionError",
    "session_id": "session_123",
    "context": "during chat"
}
```

---

## Configuration File

Hooks can be configured in `hooks.json`:

```json
{
    "version": "1.0",
    "settings": {
        "timezone": "UTC",
        "capture_tools": true
    },
    "hooks": {
        "on_message": {
            "enabled": true,
            "log": true
        },
        "on_error": {
            "enabled": true,
            "log": true,
            "alert": true
        }
    }
}
```

---

## Examples

### Example 1: Basic Hook

```python
from agentic_brain.hooks import HooksManager

manager = HooksManager()

def log_message(context):
    print(f"[{context.timestamp}] {context.data['content']}")

manager.register("on_message", log_message)

# Fire event
manager.fire("on_message", {
    "content": "Hello world",
    "user_id": "123"
})
```

---

### Example 2: Multiple Handlers

```python
from agentic_brain.hooks import HooksManager

manager = HooksManager()

def log_to_console(context):
    print(f"Message: {context.data['content']}")

def log_to_database(context):
    # Save to database
    pass

def send_notification(context):
    # Send alert
    pass

manager.register("on_message", log_to_console)
manager.register("on_message", log_to_database)
manager.register("on_message", send_notification)

# All three handlers fire
manager.fire("on_message", {"content": "Important"})
```

---

### Example 3: Error Handling

```python
from agentic_brain.hooks import HooksManager

manager = HooksManager()

def on_error(context):
    error = context.data['error']
    error_type = context.data.get('error_type', 'Unknown')
    
    if error_type == "ConnectionError":
        print(f"Connection issue: {error}")
    else:
        print(f"Error: {error}")

manager.register("on_error", on_error)

# Fire error event
manager.fire("on_error", {
    "error": "Could not connect to Neo4j",
    "error_type": "ConnectionError"
})
```

---

### Example 4: Session Tracking

```python
from agentic_brain.hooks import HooksManager

manager = HooksManager()
active_sessions = {}

def on_session_start(context):
    session_id = context.data['session_id']
    active_sessions[session_id] = {
        "started": context.timestamp,
        "messages": 0
    }
    print(f"Session started: {session_id}")

def on_session_end(context):
    session_id = context.data['session_id']
    duration = context.data.get('duration_seconds', 0)
    messages = context.data.get('message_count', 0)
    
    print(f"Session ended: {session_id}")
    print(f"  Duration: {duration}s")
    print(f"  Messages: {messages}")
    
    del active_sessions[session_id]

manager.register("on_session_start", on_session_start)
manager.register("on_session_end", on_session_end)

# Fire events
manager.fire("on_session_start", {"session_id": "sess_1", "user_id": "user_1"})
manager.fire("on_session_end", {
    "session_id": "sess_1",
    "duration_seconds": 300,
    "message_count": 10
})
```

---

### Example 5: Integration with Chatbot

```python
from agentic_brain import Chatbot
from agentic_brain.hooks import HooksManager

# Create hooks manager
manager = HooksManager()

# Set up handlers
def log_all_messages(context):
    with open("chat.log", "a") as f:
        f.write(f"{context.timestamp} {context.data}\n")

def alert_on_errors(context):
    print(f"⚠️  Error: {context.data['error']}")

manager.register("on_message", log_all_messages)
manager.register("on_response", log_all_messages)
manager.register("on_error", alert_on_errors)

# Use with chatbot
bot = Chatbot("support")

# Manually fire hooks (integrate with your bot)
manager.fire("on_message", {"content": "Hello", "session_id": "s1"})
response = bot.chat("Hello")
manager.fire("on_response", {"content": response, "session_id": "s1"})
```

---

### Example 6: Monitoring Dashboard

```python
from agentic_brain.hooks import HooksManager
from datetime import datetime

manager = HooksManager()

stats = {
    "messages": 0,
    "responses": 0,
    "errors": 0,
    "last_message": None,
    "last_error": None
}

def count_messages(context):
    stats["messages"] += 1
    stats["last_message"] = context.data['content']

def count_responses(context):
    stats["responses"] += 1

def count_errors(context):
    stats["errors"] += 1
    stats["last_error"] = context.data['error']

manager.register("on_message", count_messages)
manager.register("on_response", count_responses)
manager.register("on_error", count_errors)

# Simulate activity
manager.fire("on_message", {"content": "Hello"})
manager.fire("on_response", {"content": "Hi there"})
manager.fire("on_message", {"content": "Help"})

print(f"Messages: {stats['messages']}")
print(f"Responses: {stats['responses']}")
print(f"Errors: {stats['errors']}")
```

---

## Best Practices

### 1. Keep Handlers Fast
Hooks should not block. Use async or background tasks for heavy operations.

```python
# Good - fast
def log_message(context):
    print(f"Message: {context.data['content']}")

# Bad - slow, blocks conversation
def log_message(context):
    time.sleep(5)  # Don't do this!
    database.save(context.data)
```

### 2. Handle Errors in Handlers
Prevent one handler's error from affecting others.

```python
def safe_handler(context):
    try:
        # Your code
        process_event(context)
    except Exception as e:
        print(f"Handler error: {e}")
```

### 3. Use Appropriate Events
Choose the right event for your use case.

```python
# Session lifecycle: on_session_start, on_session_end
# Per-message: on_message, on_response
# Error handling: on_error
```

---

## See Also

- [Chat Module](./chat.md) - Chatbot with hooks
- [Agent Module](./agent.md) - Agent with events
- [Index](./index.md) - All modules

---

**Last Updated**: 2026-03-20  
**Status**: Production Ready ✅
