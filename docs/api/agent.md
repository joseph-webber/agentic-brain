# Agent Module API

Full-featured agent with persistent memory, voice output, and LLM routing. Combines chat, memory, and audio into a cohesive intelligent agent.

## Table of Contents
- [Agent](#agent) - Main agent class
- [AgentConfig](#agentconfig) - Configuration
- [Examples](#examples)

---

## Agent

Intelligent agent with memory, voice, and LLM capabilities.

### Signature

```python
class Agent:
    def __init__(
        self,
        name: str = "agent",
        system_prompt: Optional[str] = None,
        neo4j_uri: Optional[str] = None,
        neo4j_user: str = "neo4j",
        neo4j_password: str = "",
        memory_scope: DataScope = DataScope.PRIVATE,
        customer_id: Optional[str] = None,
        audio_enabled: bool = True,
        voice: str = "Karen",
        **kwargs,
    ) -> None:
        """Initialize agent."""
```

### Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `name` | `str` | `agent` | Agent name (for logging and identification) |
| `system_prompt` | `str` | `None` | Custom system prompt for personality |
| `neo4j_uri` | `str` | `None` | Neo4j connection URI (None for in-memory) |
| `neo4j_user` | `str` | `neo4j` | Neo4j username |
| `neo4j_password` | `str` | `""` | Neo4j password |
| `memory_scope` | `DataScope` | `PRIVATE` | Default memory scope (PUBLIC, PRIVATE, CUSTOMER) |
| `customer_id` | `str` | `None` | Customer ID (required for CUSTOMER scope) |
| `audio_enabled` | `bool` | `True` | Enable voice output |
| `voice` | `str` | `Karen` | Default voice name |

### Methods

#### `chat()`

Send message and get response.

```python
def chat(
    self,
    message: str,
    remember: bool = True,
    speak: bool = False,
    scope: Optional[DataScope] = None,
) -> str:
```

**Parameters:**
- `message` (str): User message
- `remember` (bool): Store in memory
- `speak` (bool): Speak response aloud
- `scope` (DataScope, optional): Override memory scope

**Returns:**
- `str`: Agent response

**Example:**
```python
agent = Agent(name="assistant")

# Simple message
response = agent.chat("What's the weather?")

# With memory
response = agent.chat("Remember my name is Alice", remember=True)

# Speak response
response = agent.chat("Tell me a joke", speak=True)
```

---

#### `remember()`

Explicitly store information in memory.

```python
def remember(
    self,
    content: str,
    scope: Optional[DataScope] = None,
    metadata: Optional[Dict[str, Any]] = None
) -> Memory:
```

**Parameters:**
- `content` (str): Information to remember
- `scope` (DataScope, optional): Memory scope
- `metadata` (dict, optional): Additional metadata

**Returns:**
- `Memory`: Stored memory object

**Example:**
```python
agent = Agent(name="assistant")

# Store facts
agent.remember("User's timezone is PST")
agent.remember(
    "Customer prefers evening calls",
    metadata={"category": "preference"}
)
```

---

#### `recall()`

Retrieve information from memory.

```python
def recall(
    self,
    query: str,
    scope: Optional[DataScope] = None,
    limit: int = 5
) -> List[Memory]:
```

**Parameters:**
- `query` (str): Search query
- `scope` (DataScope, optional): Limit to scope
- `limit` (int): Max results

**Returns:**
- `List[Memory]`: Matching memories

**Example:**
```python
agent = Agent(name="assistant")

memories = agent.recall("timezone")
for mem in memories:
    print(mem.content)
```

---

#### `speak()`

Speak text aloud.

```python
def speak(
    self,
    text: str,
    voice: Optional[str] = None,
    rate: int = 175
) -> None:
```

**Parameters:**
- `text` (str): Text to speak
- `voice` (str, optional): Voice name
- `rate` (int): Speech rate (100-200)

**Example:**
```python
agent = Agent(name="assistant", audio_enabled=True)
agent.speak("Hello, how can I help?")
agent.speak("This is important", voice="Alex", rate=150)
```

---

#### `get_history()`

Get conversation history.

```python
def get_history(self, limit: Optional[int] = None) -> List[Dict]:
```

**Returns:**
- List of message dictionaries

**Example:**
```python
agent = Agent(name="assistant")

agent.chat("Hello")
agent.chat("How are you?")

history = agent.get_history()
for msg in history:
    print(f"{msg['role']}: {msg['content']}")
```

---

#### `clear_history()`

Clear conversation history.

```python
def clear_history(self) -> None:
```

---

## AgentConfig

Agent configuration.

### Signature

```python
@dataclass
class AgentConfig:
    name: str = "agent"
    system_prompt: Optional[str] = None
    neo4j_uri: Optional[str] = None
    neo4j_user: str = "neo4j"
    neo4j_password: str = ""
    memory_scope: DataScope = DataScope.PRIVATE
    customer_id: Optional[str] = None
    audio_enabled: bool = True
    voice: str = "Karen"
    default_provider: Provider = Provider.OLLAMA
    default_model: str = "llama3.1:8b"
    temperature: float = 0.7
```

---

## Examples

### Example 1: Basic Agent

```python
from agentic_brain import Agent

agent = Agent(name="helper")

response = agent.chat("What can you help with?")
print(response)
```

---

### Example 2: Agent with Memory

```python
from agentic_brain import Agent

agent = Agent(
    name="assistant",
    neo4j_uri="bolt://localhost:7687",
    neo4j_password="password"
)

# Learn about user
agent.chat("My name is Bob and I work in sales")

# Recall later
response = agent.chat("What's my job?")
# -> "You work in sales."
```

---

### Example 3: Voice-Enabled Agent

```python
from agentic_brain import Agent

agent = Agent(
    name="assistant",
    audio_enabled=True,
    voice="Karen"
)

# Responses are spoken
agent.chat("Tell me a joke", speak=True)

# Or speak manually
agent.speak("Good morning!")
```

---

### Example 4: Customer-Isolated Agent

```python
from agentic_brain import Agent, DataScope

agent = Agent(
    name="support",
    neo4j_uri="bolt://localhost:7687",
    memory_scope=DataScope.CUSTOMER,
    customer_id="acme_corp"
)

# This data belongs to acme_corp only
agent.chat("We use Python for backend")
agent.remember("Customer prefers REST APIs")
```

---

### Example 5: Multi-Customer Support

```python
from agentic_brain import Agent, DataScope

def create_support_agent(customer_id):
    return Agent(
        name="support",
        neo4j_uri="bolt://localhost:7687",
        memory_scope=DataScope.CUSTOMER,
        customer_id=customer_id
    )

# Each customer gets isolated agent
agent_a = create_support_agent("customer_a")
agent_b = create_support_agent("customer_b")

# Data is completely isolated
agent_a.chat("We use Python", remember=True)
agent_b.chat("We use Go", remember=True)

# Each remembers their technology
print(agent_a.recall("technology"))  # Python
print(agent_b.recall("technology"))  # Go
```

---

## See Also

- [Chat Module](./chat.md) - Chatbot base class
- [Memory Module](./memory.md) - Memory storage
- [Index](./index.md) - All modules

---

**Last Updated**: 2026-03-20  
**Status**: Production Ready ✅
