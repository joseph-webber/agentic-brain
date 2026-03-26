# 🎯 Core Examples

> Fundamental agentic-brain capabilities - the building blocks for everything else.

## Examples

| # | Example | Description | Level |
|---|---------|-------------|-------|
| 01 | [simple_chat.py](01_simple_chat.py) | Minimal chatbot in 5 lines | 🟢 Beginner |
| 02 | [with_memory.py](02_with_memory.py) | Neo4j persistent memory | 🟢 Beginner |
| 03 | [streaming.py](03_streaming.py) | Real-time token streaming | 🟡 Intermediate |
| 04 | [multi_user.py](04_multi_user.py) | Isolated user sessions | 🟡 Intermediate |
| 05 | [rag_basic.py](05_rag_basic.py) | Document Q&A with RAG | 🟡 Intermediate |
| 06 | [custom_prompts.py](06_custom_prompts.py) | Personas and system prompts | 🟡 Intermediate |
| 06b | [cloud_loaders.py](06_cloud_loaders.py) | Load docs from S3, GCS, Azure | 🟡 Intermediate |
| 07 | [multi_agent.py](07_multi_agent.py) | Crews and workflows | 🔴 Advanced |
| 08 | [api_server.py](08_api_server.py) | FastAPI REST deployment | 🔴 Advanced |
| 09 | [websocket.py](09_websocket.py) | Real-time WebSocket chat | 🔴 Advanced |
| 10 | [with_auth.py](10_with_auth.py) | JWT authentication | 🔴 Advanced |
| 11 | [firebase_chat.py](11_firebase_chat.py) | Firebase real-time sync | 🔴 Advanced |
| 12 | [with_tracing.py](12_with_tracing.py) | Observability & tracing | 🔴 Advanced |

## Quick Start

```bash
# Simplest possible chatbot
python examples/core/01_simple_chat.py

# With persistent memory
python examples/core/02_with_memory.py

# Production API server
python examples/core/08_api_server.py
```

## Common Patterns

### Minimal Agent
```python
from agentic_brain import Agent
agent = Agent()
response = agent.chat("Hello!")
```

### Agent with Memory
```python
from agentic_brain import Agent
agent = Agent(memory="neo4j://localhost:7687")
```

### Streaming Responses
```python
for chunk in agent.stream("Tell me a story"):
    print(chunk, end="", flush=True)
```

### Multi-Agent Crews
```python
from agentic_brain import Crew, Agent
researcher = Agent(name="researcher", role="Research expert")
writer = Agent(name="writer", role="Content writer")
crew = Crew([researcher, writer])
```

## Key Features Demonstrated

- **01**: Basic Agent creation and chat
- **02**: Neo4j graph memory persistence
- **03**: Token-by-token streaming for real-time UX
- **04**: User isolation for multi-tenant apps
- **05**: RAG (Retrieval Augmented Generation)
- **06**: Custom personas and prompt engineering
- **07**: Multi-agent orchestration
- **08-10**: Production deployment patterns
- **11**: Firebase real-time sync
- **12**: Observability and debugging

## Prerequisites

- Python 3.10+
- Ollama running locally
- Neo4j (for memory examples)
- FastAPI/uvicorn (for API examples)
