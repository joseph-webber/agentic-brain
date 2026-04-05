# API Code Examples

Complete working examples for all major Agentic Brain APIs.

## Basic Chat

### Synchronous Chat

```python
from agentic_brain import Agent

agent = Agent(name="assistant")
response = agent.chat("What is machine learning?")
print(response)
# Output: Machine learning is a subset of AI that enables...
```

### Asynchronous Chat

```python
import asyncio
from agentic_brain import Agent

async def main():
    agent = Agent(name="assistant")
    response = await agent.chat_async("What is machine learning?")
    print(response)

asyncio.run(main())
```

---

## Streaming

### Stream with Print

```python
from agentic_brain import Agent

agent = Agent(name="assistant")

print("Streaming response:")
for chunk in agent.stream("Tell me a story about AI"):
    print(chunk, end="", flush=True)
print()  # newline
```

### Stream to File

```python
from agentic_brain import Agent

agent = Agent(name="assistant")

with open("story.txt", "w") as f:
    for chunk in agent.stream("Write a 500-word story"):
        f.write(chunk)

print("Story saved to story.txt")
```

### Async Stream

```python
import asyncio
from agentic_brain import Agent

async def main():
    agent = Agent(name="assistant")
    
    print("Streaming response:")
    async for chunk in agent.stream_async("Tell me a story"):
        print(chunk, end="", flush=True)
    print()

asyncio.run(main())
```

---

## Sessions & Memory

### Create and Manage Sessions

```python
from agentic_brain import Agent

agent = Agent(name="assistant")

# Start a new conversation
session_id = agent.create_session(user_id="user_123")
print(f"Session created: {session_id}")

# Chat in this session
response = agent.chat("Hello", session_id=session_id)
print(response)

# Get session info
session_info = agent.get_session(session_id)
print(f"Messages in session: {session_info['message_count']}")

# List all sessions
sessions = agent.list_sessions(user_id="user_123")
for session in sessions:
    print(f"- {session['id']}: {session['message_count']} messages")

# Delete session
agent.delete_session(session_id)
print("Session deleted")
```

### Access Conversation Memory

```python
from agentic_brain import Agent, Neo4jMemory

# Create agent with memory
memory = Neo4jMemory(uri="bolt://localhost:7687")
agent = Agent(name="assistant", memory=memory)

# Have a conversation
agent.chat("My name is Alice and I work at Acme Corp")
agent.chat("I'm interested in machine learning")

# Query memory
entities = memory.get_entities()
print("Entities:", entities)
# Output: [
#   {"id": "entity_1", "type": "PERSON", "name": "Alice"},
#   {"id": "entity_2", "type": "ORG", "name": "Acme Corp"},
#   {"id": "entity_3", "type": "TOPIC", "name": "machine learning"}
# ]

topics = memory.get_topics()
print("Topics:", topics)
# Output: ["work", "technology", "machine learning"]

# Clear memory
memory.clear()
```

---

## REST API

### Python Requests

```python
import requests

BASE_URL = "http://localhost:8000"
TOKEN = "your-jwt-token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Create session
response = requests.post(
    f"{BASE_URL}/sessions",
    headers=headers,
    json={"user_id": "user_123"}
)
session_id = response.json()["session_id"]
print(f"Session: {session_id}")

# Send message
response = requests.post(
    f"{BASE_URL}/chat",
    headers=headers,
    json={
        "message": "Hello!",
        "session_id": session_id
    }
)
result = response.json()
print(f"Response: {result['message']}")

# List messages
response = requests.get(
    f"{BASE_URL}/sessions/{session_id}/messages",
    headers=headers
)
messages = response.json()["messages"]
for msg in messages:
    print(f"{msg['role']}: {msg['content']}")
```

### Async with httpx

```python
import asyncio
import httpx

BASE_URL = "http://localhost:8000"
TOKEN = "your-jwt-token"

async def main():
    async with httpx.AsyncClient() as client:
        headers = {"Authorization": f"Bearer {TOKEN}"}
        
        # Send chat message
        response = await client.post(
            f"{BASE_URL}/chat",
            headers=headers,
            json={"message": "Hello!"}
        )
        print(response.json()["message"])

asyncio.run(main())
```

### JavaScript/Fetch API

```javascript
const BASE_URL = "http://localhost:8000";
const TOKEN = "your-jwt-token";

const headers = {
  "Authorization": `Bearer ${TOKEN}`,
  "Content-Type": "application/json"
};

// Send chat message
async function chat(message) {
  const response = await fetch(`${BASE_URL}/chat`, {
    method: "POST",
    headers: headers,
    body: JSON.stringify({ message })
  });
  
  const data = await response.json();
  console.log("Response:", data.message);
}

chat("Hello!");
```

---

## Streaming Responses

### Server-Sent Events (SSE)

```python
import requests

BASE_URL = "http://localhost:8000"
TOKEN = "your-jwt-token"

headers = {"Authorization": f"Bearer {TOKEN}"}

# Stream response
response = requests.get(
    f"{BASE_URL}/chat/stream",
    headers=headers,
    params={"message": "Tell me a story"},
    stream=True
)

for line in response.iter_lines():
    if line:
        print(line.decode())
```

### JavaScript EventSource

```javascript
const BASE_URL = "http://localhost:8000";
const TOKEN = "your-jwt-token";

const eventSource = new EventSource(
  `${BASE_URL}/chat/stream?message=Tell+me+a+story&token=${TOKEN}`
);

eventSource.onmessage = (event) => {
  const data = JSON.parse(event.data);
  console.log("Chunk:", data.delta);
};

eventSource.onerror = (error) => {
  console.error("Connection error:", error);
  eventSource.close();
};
```

---

## WebSocket

### Python WebSocket

```python
import asyncio
import json
import websockets

async def main():
    token = "your-jwt-token"
    session_id = "sess_123"
    
    uri = f"ws://localhost:8000/ws?session_id={session_id}&token={token}"
    
    async with websockets.connect(uri) as websocket:
        # Send message
        await websocket.send(json.dumps({
            "type": "message",
            "content": "Hello!"
        }))
        
        # Receive response
        response = await websocket.recv()
        print("Response:", json.loads(response))
        
        # Keep connection open and listen
        while True:
            message = await websocket.recv()
            print("Received:", json.loads(message))

asyncio.run(main())
```

### JavaScript WebSocket

```javascript
const token = "your-jwt-token";
const sessionId = "sess_123";

const ws = new WebSocket(
  `ws://localhost:8000/ws?session_id=${sessionId}&token=${token}`
);

ws.onopen = () => {
  console.log("Connected");
  ws.send(JSON.stringify({
    type: "message",
    content: "Hello!"
  }));
};

ws.onmessage = (event) => {
  const message = JSON.parse(event.data);
  console.log("Received:", message);
};

ws.onerror = (error) => {
  console.error("Error:", error);
};

ws.onclose = () => {
  console.log("Disconnected");
};
```

---

## RAG (Retrieval-Augmented Generation)

### Index Documents

```python
from agentic_brain.rag import RAGPipeline

rag = RAGPipeline()

# Index PDF
rag.index_file(
    "documents.pdf",
    index_name="my_docs",
    chunk_size=1024
)

# Index from text
documents = [
    {
        "id": "doc_1",
        "content": "Machine learning enables computers to learn...",
        "metadata": {"source": "article"}
    },
    {
        "id": "doc_2",
        "content": "Deep learning uses neural networks...",
        "metadata": {"source": "article"}
    }
]
rag.index_documents(documents, index_name="my_docs")
```

### Query Documents

```python
from agentic_brain.rag import RAGPipeline

rag = RAGPipeline()

# Query indexed documents
results = rag.query(
    "What is machine learning?",
    index_name="my_docs",
    top_k=5
)

for result in results:
    print(f"Score: {result['score']:.2f}")
    print(f"Content: {result['content']}")
    print()
```

### RAG with Agent

```python
from agentic_brain import Agent
from agentic_brain.rag import RAGPipeline

rag = RAGPipeline()
rag.index_file("knowledge.pdf", index_name="docs")

agent = Agent(name="assistant", rag_pipeline=rag)

# Agent uses RAG for context
response = agent.chat("What does the documentation say about X?")
print(response)
```

---

## Configuration

### Load Configuration

```python
from agentic_brain.config import load_config, Settings

# Load from file
config = load_config("brain-config.yaml")

# Load from environment
config = Settings.from_env()

# Create custom config
config = Settings(
    llm={
        "provider": "ollama",
        "model": "llama3.1:8b",
        "temperature": 0.7
    },
    memory={
        "type": "neo4j",
        "uri": "bolt://localhost:7687"
    }
)

print(f"Provider: {config.llm.provider}")
print(f"Model: {config.llm.model}")
```

### Set Configuration at Runtime

```python
from agentic_brain import Agent

agent = Agent(name="assistant")

# Override settings
agent.set_temperature(0.5)
agent.set_model("gpt-4")
agent.set_system_prompt("You are a Python expert")
```

---

## Error Handling

### Try-Except Patterns

```python
from agentic_brain import Agent
from agentic_brain.exceptions import (
    AgentError,
    MemoryError,
    RateLimitError,
    ValidationError
)

agent = Agent(name="assistant")

try:
    response = agent.chat("Hello")
except ValidationError as e:
    print(f"Invalid input: {e}")
except RateLimitError:
    print("Rate limit exceeded, retry in 60 seconds")
except MemoryError as e:
    print(f"Memory error: {e}")
except AgentError as e:
    print(f"Agent error: {e}")
    
```

### Async Error Handling

```python
import asyncio
from agentic_brain import Agent
from agentic_brain.exceptions import AgentError

async def safe_chat():
    agent = Agent(name="assistant")
    
    try:
        response = await agent.chat_async("Hello")
        return response
    except AgentError as e:
        print(f"Error: {e}")
        # Retry or fallback
        return None

result = asyncio.run(safe_chat())
```

---

## Advanced: Custom Agent

### Extend Agent Class

```python
from agentic_brain import Agent

class DateAnalysisAgent(Agent):
    """Agent specialized in date and time analysis."""
    
    def __init__(self):
        super().__init__(
            name="date_analyzer",
            system_prompt="""You are an expert in date and time analysis.
            Provide accurate date calculations and timezone conversions."""
        )
    
    def analyze_date_range(self, start_date, end_date):
        """Analyze a date range."""
        prompt = f"""Analyze the date range from {start_date} to {end_date}.
        Calculate:
        1. Number of days
        2. Number of weekdays
        3. Any holidays in between"""
        return self.chat(prompt)
    
    def timezone_convert(self, time_str, from_tz, to_tz):
        """Convert time between timezones."""
        prompt = f"Convert {time_str} from {from_tz} to {to_tz}"
        return self.chat(prompt)

# Use custom agent
agent = DateAnalysisAgent()
analysis = agent.analyze_date_range("2026-01-01", "2026-12-31")
print(analysis)
```

---

## Testing

### Unit Tests

```python
import pytest
from agentic_brain import Agent

@pytest.fixture
def agent():
    return Agent(name="test_agent")

def test_chat(agent):
    """Test basic chat functionality."""
    response = agent.chat("Hello")
    assert isinstance(response, str)
    assert len(response) > 0

@pytest.mark.asyncio
async def test_chat_async(agent):
    """Test async chat."""
    response = await agent.chat_async("Hello")
    assert isinstance(response, str)

def test_stream(agent):
    """Test response streaming."""
    chunks = list(agent.stream("Tell me a short sentence"))
    assert len(chunks) > 0
    full_response = "".join(chunks)
    assert len(full_response) > 0

@pytest.mark.asyncio
async def test_concurrent_chats(agent):
    """Test concurrent chat requests."""
    import asyncio
    tasks = [
        agent.chat_async("Hello"),
        agent.chat_async("Hi"),
        agent.chat_async("Hey")
    ]
    responses = await asyncio.gather(*tasks)
    assert len(responses) == 3
```

### Integration Tests

```python
import pytest
import requests

BASE_URL = "http://localhost:8000"
TOKEN = "test-token"

@pytest.fixture
def headers():
    return {"Authorization": f"Bearer {TOKEN}"}

def test_api_health(headers):
    """Test API health endpoint."""
    response = requests.get(f"{BASE_URL}/health", headers=headers)
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"

def test_full_chat_flow(headers):
    """Test complete chat workflow."""
    # Create session
    resp1 = requests.post(f"{BASE_URL}/sessions", headers=headers)
    session_id = resp1.json()["session_id"]
    
    # Send message
    resp2 = requests.post(
        f"{BASE_URL}/chat",
        headers=headers,
        json={"message": "Hello", "session_id": session_id}
    )
    assert resp2.status_code == 200
    
    # Get messages
    resp3 = requests.get(
        f"{BASE_URL}/sessions/{session_id}/messages",
        headers=headers
    )
    messages = resp3.json()["messages"]
    assert len(messages) > 0
```

---

## See Also

- [Python SDK Reference](./PYTHON_API.md)
- [REST API Documentation](./REST_API.md)
- [CLI Reference](./CLI_API.md)
