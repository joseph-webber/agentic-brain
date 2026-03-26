# Agentic Brain API Reference

Welcome to the Agentic Brain API documentation. This reference covers the complete public API for building intelligent agents with persistent memory, LLM routing, and enterprise features.

## Core Modules

Agentic Brain is organized into focused, composable modules:

### 🗨️ **Chat Module**
High-level chatbot with session persistence and memory integration.

- **[chat.md](./chat.md)** - Chatbot, ChatConfig, Session management
- Best for: Customer support, conversational AI, chatbots
- Key classes: `Chatbot`, `ChatConfig`, `Session`, `SessionManager`, `ChatMessage`

### 🧠 **Memory Module**
Persistent knowledge storage with Neo4j backend and data isolation.

- **[memory.md](./memory.md)** - Neo4jMemory, DataScope, Memory retrieval
- Best for: Long-term knowledge storage, multi-tenant isolation
- Key classes: `Neo4jMemory`, `DataScope`, `Memory`

### 🔍 **RAG Module**
Retrieval-augmented generation for question-answering over documents.

- **[rag.md](./rag.md)** - RAGPipeline, Retriever, EmbeddingProvider
- Best for: Document Q&A, knowledge bases, citation generation
- Key classes: `RAGPipeline`, `Retriever`, `RetrievedChunk`, `RAGResult`

### 🤖 **Agent Module**
Full-featured agent with memory, voice, and LLM capabilities.

- **[agent.md](./agent.md)** - Agent, AgentConfig
- Best for: Complex workflows, multi-step reasoning, voice integration
- Key classes: `Agent`, `AgentConfig`

### 🎣 **Hooks Module**
Lifecycle event system for extensibility.

- **[hooks.md](./hooks.md)** - HooksManager, HookContext, event registration
- Best for: Custom integrations, monitoring, event-driven workflows
- Key classes: `HooksManager`, `HookContext`

### 💼 **Business Models**
E-commerce and retail entity models with Neo4j integration.

- **[business.md](./business.md)** - Product, Order, Customer, and more
- Best for: E-commerce, inventory management, order processing
- Key classes: `Product`, `Order`, `Customer`, `BusinessEntity`

---

## Quick Start Examples

### Simple Chatbot
```python
from agentic_brain import Chatbot

bot = Chatbot("assistant")
response = bot.chat("Hello!")
print(response)
```

### Chatbot with Memory
```python
from agentic_brain import Chatbot, Neo4jMemory

memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password"
)

bot = Chatbot("support", memory=memory)
response = bot.chat("Remember my name is Alice")
```

### Document Q&A
```python
from agentic_brain import RAGPipeline

rag = RAGPipeline(neo4j_uri="bolt://localhost:7687")
result = rag.query("What is the deployment process?")
print(result.answer)
print(result.format_with_citations())
```

### Full-Featured Agent
```python
from agentic_brain import Agent, DataScope

agent = Agent(
    name="assistant",
    neo4j_uri="bolt://localhost:7687",
    neo4j_password="password",
    memory_scope=DataScope.PRIVATE,
    audio_enabled=True
)

response = agent.chat("What's today's weather?", speak=True)
```

### Business Models
```python
from agentic_brain import Product, Order, Customer

product = Product(
    sku="PROD-001",
    name="Widget",
    price=19.99,
    stock_quantity=100
)

customer = Customer(
    email="alice@example.com",
    name="Alice"
)

order = Order(
    customer_id=customer.id,
    items=[product]
)
```

---

## Design Principles

### 1. **Zero Config by Default**
All components work out of the box with sensible defaults. Override only what you need.

```python
# Just works
bot = Chatbot("assistant")

# Or customize
config = ChatConfig(max_history=200, temperature=0.5)
bot = Chatbot("assistant", config=config)
```

### 2. **Composition Over Inheritance**
Components are designed to be combined flexibly. Use them standalone or together.

```python
# Standalone chat
bot = Chatbot("assistant")

# With memory
bot = Chatbot("assistant", memory=Neo4jMemory())

# With custom LLM
bot = Chatbot("assistant", llm=my_llm_function)

# With hooks
bot = Chatbot("assistant", on_message=my_handler)
```

### 3. **Type Safety**
Full type hints for IDE autocomplete and type checking.

```python
from agentic_brain import ChatConfig, DataScope

config: ChatConfig = ChatConfig()
scope: DataScope = DataScope.CUSTOMER
```

### 4. **Data Isolation**
Multi-tenant support via data scopes. Perfect for SaaS and B2B applications.

```python
memory = Neo4jMemory()

# Each customer's data is isolated
memory.store("customer_a_data", scope=DataScope.CUSTOMER, customer_id="a")
memory.store("customer_b_data", scope=DataScope.CUSTOMER, customer_id="b")
```

---

## Configuration

Most components support both file-based and programmatic configuration.

### Environment Variables
```bash
export NEO4J_URI="bolt://localhost:7687"
export NEO4J_USER="neo4j"
export NEO4J_PASSWORD="password"
export OLLAMA_BASE_URL="http://localhost:11434"
```

### Programmatic Configuration
```python
from agentic_brain import ChatConfig, AgentConfig

# Chat configuration
chat_config = ChatConfig(
    max_history=200,
    temperature=0.7,
    persist_sessions=True,
    customer_isolation=True
)

# Agent configuration
agent_config = AgentConfig(
    name="support",
    neo4j_uri="bolt://localhost:7687",
    memory_scope=DataScope.CUSTOMER,
    audio_enabled=True
)
```

---

## Common Patterns

### Session Management
Sessions automatically persist to disk and survive restarts.

```python
bot = Chatbot("assistant")

# Conversation with same session ID persists
response1 = bot.chat("My name is Alice", session_id="user_123")
response2 = bot.chat("What's my name?", session_id="user_123")
# -> "Your name is Alice"
```

### Customer Isolation
Use data scopes for secure multi-tenant applications.

```python
bot = Chatbot("support", config=ChatConfig.business())

# Each customer is isolated
bot.chat("Help me", user_id="customer_a")
bot.chat("Help me", user_id="customer_b")
```

### Memory and Context
Automatically retrieve relevant context from memory.

```python
memory = Neo4jMemory()
bot = Chatbot("support", memory=memory)

# Store facts
bot.chat("Remember: customer prefers email contact")

# Automatically retrieve context in future conversations
bot.chat("What's the best way to contact them?")
# -> Uses stored preference
```

### Hooks and Events
Hook into the lifecycle for monitoring and custom logic.

```python
def on_message(msg):
    print(f"User: {msg.content}")

def on_response(msg):
    print(f"Bot: {msg.content}")

bot = Chatbot(
    "assistant",
    on_message=on_message,
    on_response=on_response
)
```

---

## API Patterns

### Naming Conventions
- `get_*()` - Retrieve existing data (may return None)
- `create_*()` - Create new entities
- `search_*()` - Search with query parameters
- `store_*()` - Persist data
- `retrieve_*()` - Get from storage

### Return Values
- Methods return specific types or raise exceptions
- No "status code" semantics - exceptions indicate errors
- Optional results return `None`, not sentinel values

### Configuration Objects
- Use dataclasses for configuration (`ChatConfig`, `AgentConfig`)
- Immutable after creation (use `replace()` to modify)
- Pre-built configurations available (e.g., `ChatConfig.business()`)

---

## Error Handling

Agentic Brain uses exceptions for error signaling. All exceptions are subclasses of `AgenticBrainError`.

```python
from agentic_brain import Chatbot

try:
    bot = Chatbot("assistant")
    response = bot.chat("Hello")
except Exception as e:
    print(f"Error: {e}")
```

---

## Performance Notes

### Memory Usage
- Sessions are lazily loaded and kept in memory
- Use `clear_session()` to free memory for old sessions
- Neo4j memory backend is optimized for millions of entities

### Query Performance
- Vector searches use indexing for O(1) lookup
- BM25 ranking for hybrid search
- Results are cached by default (4 hour TTL)

### Scaling
For large-scale deployments:
- Use Neo4j Enterprise for clustering
- Enable read replicas for high-concurrency
- Use connection pooling (built-in)
- See `brain-core` for MLX acceleration and streaming responses

---

## See Also

- **[Examples](../../examples/)** - Complete working examples
- **[CLI Guide](../../README.md#cli)** - Command-line interface
- **[Docker Setup](../../DOCKER_SETUP.md)** - Container deployment
- **[Architecture](../../ARCHITECTURE.md)** - System design
- **[Enterprise Features](https://github.com/joseph-webber/brain-core)** - Advanced capabilities

---

## Support

- 📖 [Documentation](../../README.md)
- 🐛 [Issues](https://github.com/joseph-webber/agentic-brain/issues)
- 💬 [Discussions](https://github.com/joseph-webber/agentic-brain/discussions)

---

**Version**: 1.0  
**Last Updated**: 2026-03-20  
**License**: Apache-2.0
