# Chat

Production-ready chatbot with session persistence, Neo4j memory, and multi-user support.

## Components

- **chatbot.py** - Main `Chatbot` class with conversation management
- **session.py** - `SessionManager` and `Session` for persistence
- **config.py** - `ChatConfig` for chatbot configuration
- **atmosphere_transport_manager.py** - Multi-transport communication manager

## Key Features

- Session persistence (survives restarts)
- Neo4j memory integration for context awareness
- Conversation threading with message history
- Multi-user support with data isolation
- Simple, clean API
- Customizable chatbot personalities
- Message caching and optimization

## Quick Start

```python
from agentic_brain.chat import Chatbot

# Simple chatbot
bot = Chatbot("assistant")
response = bot.chat("Hello!")
print(response)

# With memory across sessions
from agentic_brain import Neo4jMemory
from agentic_brain.chat import Chatbot

memory = Neo4jMemory()
bot = Chatbot("support", memory=memory)

# Bot remembers across sessions
bot.chat("My order number is 12345")
# Later...
response = bot.chat("What was my order number?")  # Knows it's 12345
```

## Multi-User Support

```python
# Each customer gets isolated context
bot = Chatbot("support", memory=memory)

# Customer 1
response1 = bot.chat("I need help", user_id="customer_1")

# Customer 2 - different context
response2 = bot.chat("I need help", user_id="customer_2")

# Retrieve conversation
history = bot.get_history(user_id="customer_1")
```

## Configuration

```python
from agentic_brain.chat import ChatConfig, Chatbot

config = ChatConfig(
    name="support",
    system_prompt="You are a helpful support agent",
    max_history=20
)
bot = Chatbot(config=config)
```

## See Also

- [RAG Integration](../rag/README.md) - Add retrieval to chat
- [Plugins System](../plugins/README.md) - Extend chatbot with plugins
- [Hooks System](../hooks/README.md) - Hook into chat lifecycle
