# Agentic Brain Architecture

**Complete system architecture documentation with diagrams.**

---

## 📐 High-Level Architecture

The Agentic Brain is built as a layered system with clear separation of concerns:

```mermaid
graph TB
    subgraph Clients
        Web[Web Browser]
        Mobile[Mobile App]
        CLI[CLI Tool]
    end

    subgraph API Layer
        FastAPI[FastAPI Server]
        Auth[Authentication]
        RateLimit[Rate Limiting]
    end

    subgraph Core
        Agent[Agent Engine]
        Router[LLM Router]
        Memory[Memory Controller]
        RAG[RAG Engine]
    end

    subgraph Transport
        WS[WebSocket]
        SSE[SSE]
        Firebase[Firebase]
    end

    subgraph Storage
        Neo4j[(Neo4j Graph)]
        Redis[(Redis Cache)]
        Vector[(Vector Store)]
    end

    subgraph LLM Providers
        Ollama[Ollama Local]
        OpenAI[OpenAI API]
        Anthropic[Anthropic API]
    end

    Web --> FastAPI
    Mobile --> FastAPI
    CLI --> FastAPI
    
    FastAPI --> Auth
    Auth --> Agent
    
    Agent --> Router
    Agent --> Memory
    Agent --> RAG
    
    Router --> Ollama
    Router --> OpenAI
    Router --> Anthropic
    
    Memory --> Neo4j
    Memory --> Redis
    RAG --> Vector
    
    Agent --> WS
    Agent --> SSE
    Agent --> Firebase

    classDef client fill:#e1f5fe
    classDef api fill:#fff3e0
    classDef core fill:#e8f5e9
    classDef storage fill:#fce4ec
    classDef llm fill:#f3e5f5
    
    class Web,Mobile,CLI client
    class FastAPI,Auth,RateLimit api
    class Agent,Router,Memory,RAG core
    class Neo4j,Redis,Vector storage
    class Ollama,OpenAI,Anthropic llm
```

---

## 🔄 Request Flow

Every chat request follows this sequence:

```mermaid
sequenceDiagram
    autonumber
    participant C as Client
    participant API as FastAPI
    participant Auth as Auth Layer
    participant Agent as Agent
    participant Memory as Neo4j Memory
    participant Router as LLM Router
    participant LLM as LLM Provider

    C->>+API: POST /chat {message, user_id}
    API->>+Auth: Validate JWT/API Key
    Auth-->>-API: ✓ Valid
    
    API->>+Agent: chat(message, user_id)
    
    Note over Agent,Memory: Context Retrieval
    Agent->>+Memory: get_context(user_id)
    Memory-->>-Agent: [past messages, facts, preferences]
    
    Note over Agent,LLM: LLM Inference
    Agent->>Agent: Build prompt with context
    Agent->>+Router: generate(prompt, model)
    Router->>+LLM: API call
    LLM-->>-Router: response tokens
    Router-->>-Agent: response text
    
    Note over Agent,Memory: Memory Storage
    Agent->>+Memory: store(user_id, message, response)
    Memory-->>-Agent: ✓ Stored
    
    Agent-->>-API: response
    API-->>-C: {response, session_id}
```

---

## 🧠 Memory Architecture

### Memory Scopes

The brain supports three levels of memory isolation:

```mermaid
graph TB
    subgraph "Memory Hierarchy"
        direction TB
        
        subgraph Public["🌐 Public Memory"]
            PubFacts[Shared Facts]
            PubKnowledge[Knowledge Base]
            PubRules[System Rules]
        end
        
        subgraph User["👤 User Memory"]
            UserPrefs[Preferences]
            UserFacts[Personal Facts]
            UserHistory[Long-term History]
        end
        
        subgraph Session["💬 Session Memory"]
            SessionMsgs[Current Messages]
            SessionCtx[Active Context]
            SessionTemp[Temporary State]
        end
    end
    
    Agent[Agent] --> Public
    Agent --> User
    Agent --> Session
    
    Public -.->|"Read-only"| Agent
    User -->|"Read/Write"| Agent
    Session -->|"Ephemeral"| Agent

    style Public fill:#e3f2fd
    style User fill:#e8f5e9
    style Session fill:#fff8e1
```

### Neo4j Graph Schema

```mermaid
graph LR
    subgraph "Node Types"
        U((User))
        S((Session))
        M((Message))
        F((Fact))
        K((Knowledge))
    end
    
    U -->|HAS_SESSION| S
    S -->|CONTAINS| M
    M -->|NEXT| M
    U -->|HAS_FACT| F
    K -->|ABOUT| U
    M -->|EXTRACTED| F
```

---

## 🚀 Transport Layer

Real-time communication across different client types:

```mermaid
graph TB
    subgraph "Transport Manager"
        TM[TransportManager]
    end
    
    subgraph "Transports"
        WS[WebSocket Transport]
        SSE[SSE Transport]
        FB[Firebase Transport]
        HTTP[HTTP Polling]
    end
    
    subgraph "Clients"
        Browser[🌐 Browser]
        MobileApp[📱 Mobile App]
        IoT[🔌 IoT Device]
        Backend[⚙️ Backend Service]
    end
    
    TM --> WS
    TM --> SSE
    TM --> FB
    TM --> HTTP
    
    WS --> Browser
    SSE --> Browser
    FB --> MobileApp
    HTTP --> IoT
    HTTP --> Backend

    style WS fill:#4caf50,color:#fff
    style SSE fill:#2196f3,color:#fff
    style FB fill:#ff9800,color:#fff
    style HTTP fill:#9c27b0,color:#fff
```

### Streaming Sequence

```mermaid
sequenceDiagram
    participant C as Client
    participant WS as WebSocket
    participant Agent as Agent
    participant LLM as LLM

    C->>WS: Connect
    WS-->>C: Connected
    
    C->>WS: {type: "chat", message: "Hello"}
    WS->>Agent: process(message)
    
    loop Token Streaming
        Agent->>LLM: Generate
        LLM-->>Agent: token
        Agent->>WS: {type: "token", data: "..."}
        WS-->>C: token
    end
    
    Agent->>WS: {type: "done"}
    WS-->>C: Complete
```

---

## 📦 Module Structure

```mermaid
graph TB
    subgraph "src/agentic_brain/"
        Agent[agent.py<br/>Core Agent Logic]
        Router[router.py<br/>LLM Routing]
        Memory[memory.py<br/>Memory Interface]
        
        subgraph "api/"
            Routes[routes.py]
            Middleware[middleware.py]
            Deps[dependencies.py]
        end
        
        subgraph "memory/"
            Neo4jMem[neo4j_memory.py]
            Cache[cache.py]
            Vector[vector_store.py]
        end
        
        subgraph "transport/"
            WSTrans[websocket.py]
            SSETrans[sse.py]
            FirebaseTrans[firebase.py]
        end
        
        subgraph "rag/"
            Retriever[retriever.py]
            Embedder[embedder.py]
            Chunker[chunker.py]
        end
        
        subgraph "plugins/"
            PluginMgr[manager.py]
            Hooks[hooks.py]
        end
    end
    
    Agent --> Router
    Agent --> Memory
    Agent --> transport/
    Memory --> memory/
    Agent --> rag/
    Agent --> plugins/
    api/ --> Agent
```

---

## 🔐 Security Architecture

```mermaid
graph TB
    subgraph "Security Layers"
        direction TB
        
        L1[🔒 TLS/HTTPS]
        L2[🔑 JWT Authentication]
        L3[👥 RBAC Authorization]
        L4[🏢 Tenant Isolation]
        L5[📝 Audit Logging]
    end
    
    Request[Incoming Request] --> L1
    L1 --> L2
    L2 --> L3
    L3 --> L4
    L4 --> L5
    L5 --> Agent[Agent Processing]
    
    style L1 fill:#e53935,color:#fff
    style L2 fill:#fb8c00,color:#fff
    style L3 fill:#fdd835
    style L4 fill:#43a047,color:#fff
    style L5 fill:#1e88e5,color:#fff
```

---

## 🏗️ Deployment Architecture

### Docker Compose Stack

```mermaid
graph TB
    subgraph "Docker Network"
        subgraph "Application"
            API[agentic-brain:8000]
            Worker[Celery Worker]
        end
        
        subgraph "Data Stores"
            Neo4j[(Neo4j:7687)]
            Redis[(Redis:6379)]
        end
        
        subgraph "Observability"
            Prometheus[Prometheus]
            Grafana[Grafana]
        end
    end
    
    LB[Load Balancer] --> API
    API --> Neo4j
    API --> Redis
    API --> Worker
    Worker --> Neo4j
    Prometheus --> API
    Grafana --> Prometheus
```

### Production Architecture

```mermaid
graph TB
    subgraph "Cloud Provider"
        LB[Load Balancer]
        
        subgraph "Compute"
            K8s[Kubernetes Cluster]
            Pod1[Pod 1]
            Pod2[Pod 2]
            Pod3[Pod N]
        end
        
        subgraph "Managed Services"
            Neo4jAura[(Neo4j Aura)]
            ElastiCache[(Redis)]
            S3[(Object Storage)]
        end
    end
    
    Internet[🌐 Internet] --> LB
    LB --> K8s
    K8s --> Pod1
    K8s --> Pod2
    K8s --> Pod3
    
    Pod1 --> Neo4jAura
    Pod2 --> Neo4jAura
    Pod3 --> Neo4jAura
    
    Pod1 --> ElastiCache
    Pod2 --> ElastiCache
    Pod3 --> ElastiCache
```

---

## 📊 Data Flow Summary

```
┌─────────────┐     ┌─────────────┐     ┌─────────────┐
│   Client    │────▶│  FastAPI    │────▶│   Agent     │
└─────────────┘     └─────────────┘     └──────┬──────┘
                                               │
                    ┌──────────────────────────┼──────────────────────────┐
                    │                          │                          │
              ┌─────▼─────┐            ┌───────▼───────┐          ┌───────▼───────┐
              │  Router   │            │    Memory     │          │   Transport   │
              └─────┬─────┘            └───────┬───────┘          └───────┬───────┘
                    │                          │                          │
         ┌──────────┼──────────┐               │                 ┌────────┼────────┐
         │          │          │               │                 │        │        │
    ┌────▼────┐ ┌───▼───┐ ┌────▼────┐    ┌─────▼─────┐     ┌─────▼────┐ ┌─▼──┐ ┌───▼────┐
    │ Ollama  │ │OpenAI │ │Anthropic│    │   Neo4j   │     │WebSocket │ │SSE │ │Firebase│
    └─────────┘ └───────┘ └─────────┘    └───────────┘     └──────────┘ └────┘ └────────┘
```

---

## 🔗 Key Interfaces

### Agent Interface

```python
class Agent:
    def chat(message: str, user_id: str, **kwargs) -> str
    def stream(message: str, user_id: str) -> AsyncIterator[str]
    def get_context(user_id: str) -> List[Message]
    def store_fact(user_id: str, fact: str) -> None
```

### Memory Interface

```python
class Memory(Protocol):
    async def get_context(user_id: str, limit: int) -> List[Message]
    async def store_message(user_id: str, role: str, content: str) -> None
    async def get_facts(user_id: str) -> List[Fact]
    async def store_fact(user_id: str, fact: Fact) -> None
```

### Router Interface

```python
class LLMRouter:
    # Core methods
    async def generate(prompt: str, model: str = None) -> str
    async def stream(prompt: str, model: str = None) -> AsyncIterator[str]
    def available_models() -> List[str]
    
    # Provider health
    async def check_all_providers() -> dict  # Health status of all providers
    
    # HTTP pooling
    async def start_http_pool() -> None      # Manual pool start (auto-starts on use)
    async def stop_http_pool() -> None
    def get_pool_stats() -> dict             # Pool metrics
    
    # Token tracking
    def get_token_stats() -> dict            # Usage by provider
    def reset_token_stats() -> None
    
    # Context manager support
    async with LLMRouter() as router:
        await router.generate(...)           # Pool auto-managed
```

**Per-Provider Timeouts:**
| Provider | Default Timeout | Reason |
|----------|----------------|--------|
| Ollama | 120s | Local models slow on first load |
| Anthropic | 90s | Claude can be slower |
| OpenAI | 60s | Generally fast |
| OpenRouter | 60s | Multiple backends |

**HTTP Connection Pooling:**
- Pool enabled by default (`use_http_pool=True`)
- Auto-starts on first request (lazy initialization)
- Reuses keep-alive connections (~50ms → ~1ms connection setup)
- Automatic retries with circuit breaker
- Falls back to direct sessions if pool unavailable

---

## 📚 Related Documentation

- **[Getting Started](./getting-started.md)** — Quick start guide
- **[API Reference](./api/)** — Complete API documentation
- **[Streaming](./STREAMING.md)** — Real-time response streaming
- **[Plugins](./plugins.md)** — Extending functionality
- **[Security](./SECURITY.md)** — Security best practices

---

*Last updated: 2026-03-21*
