# Python SDK Reference

## Installation

```bash
pip install agentic-brain
```

## Quick Start

```python
from agentic_brain import Agent, Neo4jMemory

# Create an agent with Neo4j memory
agent = Agent(
    name="assistant",
    neo4j_uri="bolt://localhost:7687",
    neo4j_user="neo4j",
    neo4j_password="password"
)

# Chat synchronously
response = agent.chat("What is GraphRAG?")
print(response)

# Chat asynchronously
response = await agent.chat_async("Tell me more!")
print(response)
```

## Agent Class

### Overview

The `Agent` class provides a high-level interface for building AI applications with memory and LLM routing.

```python
from agentic_brain import Agent, SecurityRole, DataScope

agent = Agent(
    name="assistant",
    system_prompt="You are a helpful assistant.",
    security_role=SecurityRole.USER,
    memory_scope=DataScope.PRIVATE,
    default_provider="ollama",
    default_model="llama3.1:8b"
)
```

### Constructor Parameters

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| name | str | "agent" | Agent name |
| system_prompt | str | None | System prompt for LLM |
| security_role | SecurityRole | USER | Security role (USER, ADMIN) |
| neo4j_uri | str | None | Neo4j connection URI |
| neo4j_user | str | "neo4j" | Neo4j username |
| neo4j_password | str | "" | Neo4j password |
| memory_scope | DataScope | PRIVATE | Memory scope (PRIVATE, SHARED) |
| audio_enabled | bool | True | Enable voice output |
| voice | str | "Karen" | Voice name |
| default_provider | str | "ollama" | LLM provider |
| default_model | str | "llama3.1:8b" | LLM model |
| temperature | float | 0.7 | LLM temperature |

### Methods

#### chat(message: str) -> str

Send a synchronous chat message.

```python
response = agent.chat("Hello!")
print(response)
# Output: "Hello! How can I help you today?"
```

**Parameters:**
- `message` (str): User message (1-32000 chars)

**Returns:**
- `str`: Assistant response

**Raises:**
- `ValueError`: If message is empty
- `RuntimeError`: If agent is not initialized

---

#### async chat_async(message: str) -> str

Send an asynchronous chat message.

```python
import asyncio

async def main():
    response = await agent.chat_async("Hello!")
    print(response)

asyncio.run(main())
```

**Parameters:**
- `message` (str): User message

**Returns:**
- `Coroutine[str]`: Async task returning response

---

#### stream(message: str, *, chunk_size: int = 1024)

Stream responses as they are generated.

```python
for chunk in agent.stream("Tell me a story"):
    print(chunk, end="", flush=True)
```

**Parameters:**
- `message` (str): User message
- `chunk_size` (int): Size of response chunks

**Returns:**
- `Iterator[str]`: Response chunks

---

#### stream_async(message: str, *, chunk_size: int = 1024)

Asynchronously stream responses.

```python
async for chunk in agent.stream_async("Tell me a story"):
    print(chunk, end="", flush=True)
```

---

#### get_memory() -> Memory

Get the agent's memory object.

```python
memory = agent.get_memory()
topics = memory.get_topics()
entities = memory.get_entities()
```

**Returns:**
- `Memory`: Memory object

---

#### clear_memory()

Clear all agent memory.

```python
agent.clear_memory()
```

---

#### set_system_prompt(prompt: str)

Update the system prompt.

```python
agent.set_system_prompt(
    "You are a helpful finance assistant with expertise in investing."
)
```

---

## Memory API

### Neo4jMemory Class

Persistent graph-based memory using Neo4j.

```python
from agentic_brain import Neo4jMemory, DataScope

memory = Neo4jMemory(
    uri="bolt://localhost:7687",
    user="neo4j",
    password="password",
    scope=DataScope.SHARED
)

# Store information
memory.remember("Alice works at Acme Corp")

# Query memory
topics = memory.get_topics()
entities = memory.get_entities()
relationships = memory.get_relationships()
```

### Methods

#### remember(statement: str)

Store a fact in memory.

```python
memory.remember("The capital of France is Paris")
memory.remember("Alice and Bob are friends")
```

---

#### recall(query: str) -> list[str]

Retrieve relevant facts from memory.

```python
facts = memory.recall("What do we know about Alice?")
# Returns: ["Alice works at Acme Corp", "Alice is a software engineer"]
```

---

#### get_entities() -> list[dict]

Get all known entities.

```python
entities = memory.get_entities()
# Returns:
# [
#   {"id": "entity_1", "type": "PERSON", "name": "Alice"},
#   {"id": "entity_2", "type": "ORG", "name": "Acme Corp"}
# ]
```

---

#### get_relationships() -> list[dict]

Get all known relationships.

```python
relationships = memory.get_relationships()
# Returns:
# [
#   {"source": "Alice", "target": "Acme Corp", "type": "WORKS_AT"}
# ]
```

---

#### get_topics() -> list[str]

Get conversation topics.

```python
topics = memory.get_topics()
# Returns: ["work", "technology", "career"]
```

---

## LLM Router API

### LLMRouter Class

Route messages to different LLMs based on complexity.

```python
from agentic_brain import LLMRouter, Provider

router = LLMRouter(
    default_provider=Provider.OLLAMA,
    fallback_provider=Provider.GROQ
)

# Route and get response
response = router.route(
    prompt="What is machine learning?",
    task_type="general"
)
```

### Providers

| Provider | Speed | Quality | Local |
|----------|-------|---------|-------|
| OLLAMA | Fast | Good | Yes |
| GROQ | Very Fast | Good | No |
| CLAUDE | Medium | Excellent | No |
| OPENAI | Medium | Excellent | No |

---

## Configuration API

### Load Configuration

```python
from agentic_brain.config import load_config

config = load_config("brain-config.yaml")
print(config.llm.provider)  # "ollama"
print(config.llm.model)     # "llama3.1:8b"
```

### Configuration Schema

```python
from agentic_brain.config import Settings

settings = Settings(
    llm=LLMSettings(
        provider="ollama",
        model="llama3.1:8b",
        temperature=0.7,
        top_p=0.9,
        max_tokens=2048
    ),
    memory=MemorySettings(
        type="neo4j",
        uri="bolt://localhost:7687",
        cache_enabled=True
    ),
    security=SecuritySettings(
        audit_enabled=True,
        rate_limit=60
    )
)
```

---

## Evaluation API

### Evaluate Responses

```python
from agentic_brain.evaluation import Evaluator

evaluator = Evaluator()

# Evaluate a response
result = evaluator.evaluate(
    question="What is AI?",
    ground_truth="AI is artificial intelligence",
    answer="AI stands for artificial intelligence"
)

print(f"Score: {result.score}")  # 0.95
print(f"Metrics: {result.metrics}")
```

### Metrics

- **Relevance**: How relevant is the answer to the question?
- **Accuracy**: How accurate is the answer?
- **Completeness**: Does the answer cover all aspects?
- **Clarity**: How clear and understandable is the answer?

---

## Error Handling

### Common Exceptions

```python
from agentic_brain.exceptions import (
    AgentError,
    MemoryError,
    AuthenticationError,
    RateLimitError
)

try:
    response = agent.chat("Hello")
except AuthenticationError:
    print("Authentication failed")
except RateLimitError:
    print("Rate limit exceeded")
except AgentError as e:
    print(f"Agent error: {e}")
```

---

## Async/Await Patterns

### Concurrent Requests

```python
import asyncio
from agentic_brain import Agent

async def main():
    agent = Agent(name="assistant")
    
    # Send concurrent requests
    tasks = [
        agent.chat_async("Hello"),
        agent.chat_async("How are you?"),
        agent.chat_async("Tell me a joke")
    ]
    
    responses = await asyncio.gather(*tasks)
    print(responses)

asyncio.run(main())
```

---

## Streaming Examples

### Stream with Callbacks

```python
def on_chunk(chunk):
    print(f"Received: {chunk}")

agent.stream("Tell me a story", callback=on_chunk)
```

### Stream to File

```python
with open("response.txt", "w") as f:
    for chunk in agent.stream("Write a poem"):
        f.write(chunk)
```

---

## Advanced: Custom Agents

### Extend Agent Class

```python
from agentic_brain import Agent

class FinanceAgent(Agent):
    """Custom agent for financial analysis."""
    
    def __init__(self):
        super().__init__(
            name="finance_assistant",
            system_prompt="""You are an expert financial advisor.
            Provide accurate investment advice."""
        )
    
    def analyze_portfolio(self, holdings):
        prompt = f"Analyze this portfolio: {holdings}"
        return self.chat(prompt)

agent = FinanceAgent()
analysis = agent.analyze_portfolio([
    {"symbol": "AAPL", "shares": 10},
    {"symbol": "MSFT", "shares": 5}
])
```

---

## Performance Tips

1. **Reuse Agent Instance**: Create once, reuse many times
2. **Use Async**: Use `chat_async()` for concurrent requests
3. **Enable Caching**: Set `cache_enabled=True` in memory config
4. **Stream Long Responses**: Use `stream()` for better UX
5. **Batch Operations**: Process multiple items in one call

---

## Testing

```python
from agentic_brain import Agent
import pytest

@pytest.fixture
def agent():
    return Agent(name="test_agent")

def test_agent_chat(agent):
    response = agent.chat("Hello")
    assert isinstance(response, str)
    assert len(response) > 0

@pytest.mark.asyncio
async def test_agent_async(agent):
    response = await agent.chat_async("Hello")
    assert isinstance(response, str)
```

---

## See Also

- [REST API Documentation](./REST_API.md)
- [CLI Reference](./CLI_API.md)
- [Code Examples](./EXAMPLES.md)
- [Memory System](../MEMORY.md)
