# Hooks

Lifecycle hooks system for firing and registering events throughout the agentic-brain lifecycle.

## Components

- **hooks.py** - `HooksManager` for managing lifecycle events and `HookContext` for event data

## Key Features

- Event-driven architecture for lifecycle management
- Built-in hooks for key events (session, message, response, error)
- JSON configuration support for hook definitions
- Context data passed to handlers
- Timestamp tracking for all events
- Flexible event handling and logging

## Built-in Hook Events

- `on_session_start` - Fired when a session begins
- `on_session_end` - Fired when a session ends
- `on_message` - Fired when a message is received
- `on_response` - Fired when a response is generated
- `on_error` - Fired when an error occurs
- `on_load` - Fired when system starts
- `on_unload` - Fired when system shuts down

## Quick Start

```python
from agentic_brain.hooks import HooksManager, HookContext

# Initialize manager
hooks = HooksManager()

# Register handler
def on_message_handler(context):
    print(f"Message: {context.data}")

hooks.register('on_message', on_message_handler)

# Fire event
hooks.fire('on_message', {
    'user_id': 'user1',
    'message': 'hello'
})

# Load from JSON config
hooks.load_from_file('hooks.json')
```

## Hook Context

```python
from datetime import datetime

context = HookContext(
    event_type='on_message',
    timestamp=datetime.now(),
    data={'user_id': 'user1', 'text': 'hello'}
)

# Access data
print(context.event_type)
print(context.timestamp)
print(context.to_dict())
```

## JSON Configuration

```json
{
  "hooks": [
    {
      "event": "on_message",
      "handler": "my_handlers:log_message"
    },
    {
      "event": "on_error",
      "handler": "my_handlers:notify_admin"
    }
  ]
}
```

## See Also

- [Chat Module](../chat/README.md) - Hooks fire on chat events
- [Plugins System](../plugins/README.md) - Plugins also use hooks
- [Advanced Integration](../../../docs/tutorials/lifecycle-hooks.md)
