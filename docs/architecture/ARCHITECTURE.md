# Agentic Brain Architecture

<div align="center">

[![Architecture](https://img.shields.io/badge/Architecture-Production_Ready-00A86B?style=for-the-badge)](./ARCHITECTURE.md)
[![Zero Trust](https://img.shields.io/badge/Zero_Trust-Security-4A90D9?style=for-the-badge)](../SECURITY.md)
[![GraphRAG](https://img.shields.io/badge/GraphRAG-Enabled-9333EA?style=for-the-badge)](../RAG.md)

**Enterprise-Grade AI Infrastructure · Multi-LLM Orchestration · Graph-Enhanced RAG**

*A comprehensive technical reference for the Agentic Brain architecture.*

</div>

---

## 📋 Table of Contents

- [System Overview](#1-system-overview)
- [Component Architecture](#2-component-architecture)
- [LLM Routing Flow](#3-llm-routing-flow)
- [RAG Pipeline](#4-rag-pipeline)
- [Security Postures](#5-security-postures)
- [Data Flow](#6-data-flow)
- [Deployment Topologies](#7-deployment-topologies)
- [API Architecture](#8-api-architecture)
- [Memory System](#9-memory-system)
- [Technology Stack](#10-technology-stack)

---

## 1. System Overview

For the Neo4j-specific reference model used by GraphRAG and memory, see [Neo4j Architecture](../NEO4J_ARCHITECTURE.md) and [Neo4j Zones](../NEO4J_ZONES.md).

Agentic Brain is a **production-ready AI orchestration platform** that combines multi-LLM routing, graph-enhanced RAG, and enterprise security. The architecture follows a modular, microservices-friendly design that can scale from single-node deployments to distributed clusters.

<div align="center">
<img src="./system-overview.svg" alt="Agentic Brain System Architecture - showing CLI/API Gateway, Smart Router, LLM Providers (OpenAI, Claude, Ollama, Groq), RAG Engine, Neo4j Graph DB, Vector Store, and Redis Cache" width="800">

*High-level system architecture diagram*
</div>

```mermaid
graph TB
    subgraph "Client Layer"
        CLI[🖥️ CLI Interface]
        WEB[🌐 Web Dashboard]
        SDK[📦 Python SDK]
        MCP[🔌 MCP Server]
    end
    
    subgraph "Agentic Brain Core"
        API[⚡ FastAPI Server]
        Router[🔀 Smart LLM Router]
        RAG[🔍 GraphRAG Engine]
        Memory[🧠 Memory System]
        Voice[🎙️ Voice Engine]
        Auth[🔐 Auth Layer]
    end
    
    subgraph "LLM Providers"
        OpenAI[OpenAI GPT-4]
        Claude[Anthropic Claude]
        Ollama[Ollama Local]
        Groq[Groq]
        Azure[Azure OpenAI]
        Together[Together AI]
    end
    
    subgraph "Storage Layer"
        Neo4j[(Neo4j Graph)]
        Redis[(Redis Cache)]
        Vector[(Vector Store)]
        EventStore[(Event Store)]
    end
    
    subgraph "Infrastructure"
        Kafka[📡 Kafka/Redpanda]
        Temporal[⏱️ Temporal]
        Metrics[📊 Prometheus]
    end
    
    CLI --> API
    WEB --> API
    SDK --> API
    MCP --> API
    
    API --> Auth
    Auth --> Router
    Router --> OpenAI & Claude & Ollama & Groq & Azure & Together
    
    API --> RAG
    RAG --> Neo4j
    RAG --> Vector
    
    API --> Memory
    Memory --> Redis
    Memory --> Neo4j
    
    API --> Voice
    
    Router --> Kafka
    Memory --> EventStore
    API --> Metrics
    
    Router -.-> Temporal
```

### Key Design Principles

| Principle | Implementation |
|-----------|----------------|
| **Modularity** | Each component is independently deployable and testable |
| **Resilience** | Automatic failover, circuit breakers, retry policies |
| **Observability** | Structured logging, distributed tracing, metrics |
| **Security First** | Zero-trust architecture, encryption everywhere |
| **Hardware Acceleration** | Native support for Apple Silicon (MLX), NVIDIA CUDA, AMD ROCm |

---

## 2. Component Architecture

```mermaid
graph LR
    subgraph "API Layer"
        Routes[Routes]
        Middleware[Middleware]
        WebSocket[WebSocket]
    end
    
    subgraph "Business Logic"
        Orchestration[Orchestration]
        Skills[Skills Engine]
        Plugins[Plugin System]
        Ethics[Ethics Engine]
    end
    
    subgraph "AI Core"
        SmartRouter[Smart Router]
        RAGPipeline[RAG Pipeline]
        MemoryUnified[Unified Memory]
        VoiceEngine[Voice Engine]
    end
    
    subgraph "Infrastructure"
        Cache[Caching]
        Queue[Message Queue]
        Durability[Durability]
        Health[Health Checks]
    end
    
    Routes --> Orchestration
    Middleware --> Routes
    WebSocket --> Orchestration
    
    Orchestration --> SmartRouter
    Orchestration --> RAGPipeline
    Orchestration --> MemoryUnified
    
    Skills --> SmartRouter
    Plugins --> Skills
    Ethics --> Orchestration
    
    SmartRouter --> Cache
    RAGPipeline --> Queue
    MemoryUnified --> Durability
    
    Cache --> Health
    Queue --> Health
    Durability --> Health
```

### Core Modules

| Module | Location | Purpose |
|--------|----------|---------|
| `api/` | `src/agentic_brain/api/` | FastAPI routes, middleware, WebSocket |
| `router/` | `src/agentic_brain/router/` | Smart LLM routing with 10+ providers |
| `rag/` | `src/agentic_brain/rag/` | GraphRAG with 54+ document loaders |
| `memory/` | `src/agentic_brain/memory/` | Unified memory with Neo4j backend |
| `voice/` | `src/agentic_brain/voice/` | Multi-voice TTS with regional support |
| `auth/` | `src/agentic_brain/auth/` | OAuth2, SAML, API keys, RBAC |
| `skills/` | `src/agentic_brain/skills/` | Extensible skill system |
| `durability/` | `src/agentic_brain/durability/` | Event sourcing, task queues |

---

## 3. LLM Routing Flow

The **SmartRouter** implements intelligent multi-LLM orchestration with four primary modes:

```mermaid
flowchart TB
    subgraph "Input"
        Request[📝 User Request]
        Context[📊 Context Analysis]
    end
    
    subgraph "SmashMode Selection"
        Analyzer[🔍 Task Analyzer]
        
        subgraph "Modes"
            TURBO[⚡ TURBO<br/>Fire ALL, fastest wins]
            CASCADE[🌊 CASCADE<br/>Free → Paid fallback]
            CONSENSUS[🤝 CONSENSUS<br/>3+ compare results]
            DEDICATED[🎯 DEDICATED<br/>Best for task type]
            PARALLEL[🔀 PARALLEL<br/>Concurrent execution]
        end
    end
    
    subgraph "Worker Pool"
        OpenAI[OpenAI]
        Claude[Claude]
        Groq[Groq]
        Ollama[Ollama]
        Azure[Azure]
        Together[Together]
        DeepSeek[DeepSeek]
    end
    
    subgraph "Output"
        Aggregator[📦 Result Aggregator]
        Response[✅ Response]
    end
    
    Request --> Context
    Context --> Analyzer
    
    Analyzer -->|Speed Critical| TURBO
    Analyzer -->|Cost Sensitive| CASCADE
    Analyzer -->|High Stakes| CONSENSUS
    Analyzer -->|Task Specific| DEDICATED
    Analyzer -->|Bulk Work| PARALLEL
    
    TURBO --> OpenAI & Claude & Groq & Ollama
    CASCADE --> Ollama --> Groq --> OpenAI
    CONSENSUS --> OpenAI & Claude & Groq
    DEDICATED --> DeepSeek
    PARALLEL --> Azure & Together
    
    OpenAI & Claude & Groq & Ollama & Azure & Together & DeepSeek --> Aggregator
    Aggregator --> Response
```

### SmashMode Details

| Mode | Use Case | Behavior | Cost |
|------|----------|----------|------|
| **TURBO** | Speed critical | Fire all workers simultaneously, return fastest | High |
| **CASCADE** | Cost optimization | Try free (Ollama) → cheap (Groq) → premium (OpenAI) | Low |
| **CONSENSUS** | High-stakes decisions | Query 3+ LLMs, compare/vote on results | Medium |
| **DEDICATED** | Task-specific routing | Route to best model for task type | Variable |
| **PARALLEL** | Bulk processing | Distribute work across workers | Medium |

### Task-to-Model Routing

```python
TASK_ROUTES = {
    "code": ["openai", "azure_openai", "groq", "local"],
    "fast": ["groq", "gemini", "local"],
    "free": ["gemini", "groq", "local", "together"],
    "bulk": ["local", "together", "groq"],
    "complex": ["openai", "deepseek", "groq"],
    "creative": ["openai", "gemini", "groq"],
}
```

---

## 4. RAG Pipeline

The **GraphRAG Engine** combines vector similarity search with knowledge graph traversal for superior retrieval accuracy.

```mermaid
flowchart LR
    subgraph "Query Processing"
        Query[📝 Query]
        Embedding[🔢 Embedding<br/>MLX/CUDA accelerated]
        Intent[🎯 Intent Detection]
    end
    
    subgraph "Retrieval Layer"
        VectorSearch[🔍 Vector Search<br/>Top-K similarity]
        GraphTraversal[🕸️ Graph Traversal<br/>Neo4j relationships]
        BM25[📚 BM25 Keyword<br/>Hybrid search]
    end
    
    subgraph "Ranking Layer"
        Fusion[🔀 Score Fusion<br/>RRF/Linear]
        Reranker[🏆 Cross-Encoder<br/>Reranking]
        MMR[🌈 MMR<br/>Diversity]
    end
    
    subgraph "Context Building"
        Chunking[📄 Smart Chunking]
        Citation[📌 Source Citation]
        Confidence[📊 Confidence Scores]
    end
    
    subgraph "Response Generation"
        Context[📋 Augmented Context]
        LLM[🤖 LLM Generation]
        Response[✅ Response + Sources]
    end
    
    Query --> Embedding
    Query --> Intent
    
    Embedding --> VectorSearch
    Intent --> GraphTraversal
    Query --> BM25
    
    VectorSearch --> Fusion
    GraphTraversal --> Fusion
    BM25 --> Fusion
    
    Fusion --> Reranker
    Reranker --> MMR
    
    MMR --> Chunking
    Chunking --> Citation
    Citation --> Confidence
    
    Confidence --> Context
    Context --> LLM
    LLM --> Response
```

### RAG Features

| Feature | Description |
|---------|-------------|
| **Hardware Acceleration** | MLX (Apple M1-M4), CUDA (NVIDIA), ROCm (AMD) |
| **Chunking Strategies** | Fixed, Semantic, Recursive, Markdown-aware |
| **Hybrid Search** | Vector + BM25 keyword with RRF fusion |
| **Reranking** | Cross-encoder, MMR for diversity |
| **54+ Loaders** | Google Drive, Gmail, S3, Confluence, Notion, Slack... |
| **Graph Enhancement** | Neo4j relationship traversal for contextual depth |

### Embedding Pipeline

```mermaid
graph TB
    subgraph "Input"
        Text[📄 Text Input]
        Config[⚙️ Model Config]
    end
    
    subgraph "Hardware Detection"
        Detect{🔍 Detect Hardware}
        MLX[🍎 Apple MLX]
        CUDA[🟢 NVIDIA CUDA]
        ROCm[🔴 AMD ROCm]
        CPU[💻 CPU Fallback]
    end
    
    subgraph "Model Loading"
        Model[🤖 sentence-transformers]
        Cache[📦 Model Cache]
    end
    
    subgraph "Output"
        Embedding[🔢 Embedding Vector]
        Metadata[📊 Metadata]
    end
    
    Text --> Detect
    Config --> Model
    
    Detect -->|M1-M4| MLX
    Detect -->|NVIDIA| CUDA
    Detect -->|AMD| ROCm
    Detect -->|Other| CPU
    
    MLX --> Model
    CUDA --> Model
    ROCm --> Model
    CPU --> Model
    
    Cache --> Model
    Model --> Embedding
    Model --> Metadata
```

---

## 5. Security Postures

Agentic Brain supports **six security postures** ranging from open consumer use to classified government operations.

```mermaid
graph TB
    subgraph "Security Postures"
        direction TB
        
        Consumer[🏠 CONSUMER<br/>Open, minimal restrictions]
        Professional[💼 PROFESSIONAL<br/>Standard business security]
        Enterprise[🏢 ENTERPRISE<br/>Corporate compliance]
        Defense[🛡️ DEFENSE<br/>Government contractor]
        TopSecret[🔒 TOP SECRET<br/>Classified operations]
        SCIF[🏛️ SCIF<br/>Air-gapped, no external APIs]
    end
    
    Consumer --> Professional
    Professional --> Enterprise
    Enterprise --> Defense
    Defense --> TopSecret
    TopSecret --> SCIF
    
    style Consumer fill:#10B981
    style Professional fill:#3B82F6
    style Enterprise fill:#8B5CF6
    style Defense fill:#F59E0B
    style TopSecret fill:#EF4444
    style SCIF fill:#1F2937
```

### Posture Comparison Matrix

| Posture | External APIs | Logging | PII Handling | LLM Workers | Auth Level |
|---------|---------------|---------|--------------|-------------|------------|
| **Consumer** | ✅ All | Minimal | Basic redaction | All | API Key |
| **Professional** | ✅ Approved | Standard | Enhanced redaction | Approved | OAuth2 |
| **Enterprise** | ⚠️ Vetted only | Full audit | Field-level encryption | Enterprise tier | SAML/SSO |
| **Defense** | ⚠️ FedRAMP only | Immutable logs | E2E encryption | FedRAMP certified | CAC/PIV |
| **Top Secret** | ❌ Gov cloud only | Air-gapped logs | HSM encryption | Classified only | MFA + biometric |
| **SCIF** | ❌ None | Local only | Full isolation | Local only | Physical + MFA |

### Security Configuration

```mermaid
graph LR
    subgraph "Access Control"
        RBAC[🔐 RBAC]
        ABAC[🏷️ ABAC]
        Tenant[🏢 Tenant Isolation]
    end
    
    subgraph "Data Protection"
        Encrypt[🔒 AES-256-GCM]
        TLS[🛡️ TLS 1.3]
        KMS[🔑 KMS/HSM]
    end
    
    subgraph "Monitoring"
        Audit[📋 Audit Logs]
        SIEM[📡 SIEM Integration]
        Alert[🚨 Alerting]
    end
    
    RBAC --> Encrypt
    ABAC --> Encrypt
    Tenant --> TLS
    
    Encrypt --> Audit
    TLS --> SIEM
    KMS --> Alert
```

---

## 6. Data Flow

Complete request lifecycle from client to response:

```mermaid
sequenceDiagram
    participant Client
    participant API as FastAPI
    participant Auth
    participant Router as SmartRouter
    participant RAG
    participant LLM
    participant Memory
    participant Neo4j
    participant Redis
    
    Client->>API: POST /chat
    API->>Auth: Validate JWT/API Key
    Auth-->>API: ✅ Authorized
    
    API->>Memory: Check conversation context
    Memory->>Redis: Get cached context
    Redis-->>Memory: Context data
    Memory-->>API: Conversation history
    
    API->>RAG: Query with context
    RAG->>Neo4j: Graph traversal
    Neo4j-->>RAG: Related entities
    RAG->>RAG: Vector search + rerank
    RAG-->>API: Augmented context
    
    API->>Router: Route to best LLM
    Router->>Router: Select SmashMode
    Router->>LLM: Generate response
    LLM-->>Router: LLM response
    Router-->>API: Final response
    
    API->>Memory: Store interaction
    Memory->>Neo4j: Persist memory node
    Memory->>Redis: Update cache
    
    API-->>Client: Response + sources
```

### Event Flow

```mermaid
flowchart LR
    subgraph "Event Sources"
        API[API Events]
        Router[Router Events]
        RAG[RAG Events]
        Memory[Memory Events]
    end
    
    subgraph "Event Bus"
        Kafka[📡 Kafka/Redpanda]
    end
    
    subgraph "Consumers"
        Analytics[📊 Analytics]
        Audit[📋 Audit Log]
        Learning[🧠 Learning Engine]
        Alerts[🚨 Alerting]
    end
    
    API --> Kafka
    Router --> Kafka
    RAG --> Kafka
    Memory --> Kafka
    
    Kafka --> Analytics
    Kafka --> Audit
    Kafka --> Learning
    Kafka --> Alerts
```

---

## 7. Deployment Topologies

```mermaid
graph TB
    subgraph "Single Node (Development)"
        Dev[💻 All-in-One<br/>API + RAG + Memory]
        DevDB[(SQLite/Local Neo4j)]
        Dev --> DevDB
    end
    
    subgraph "Standard (Production)"
        LB[⚖️ Load Balancer]
        
        subgraph "API Cluster"
            API1[API Node 1]
            API2[API Node 2]
            API3[API Node 3]
        end
        
        subgraph "Data Layer"
            Neo4jCluster[(Neo4j Cluster)]
            RedisCluster[(Redis Cluster)]
        end
        
        LB --> API1 & API2 & API3
        API1 & API2 & API3 --> Neo4jCluster & RedisCluster
    end
    
    subgraph "Enterprise (High Availability)"
        direction TB
        CDN[🌐 CDN]
        WAF[🛡️ WAF]
        
        subgraph "Region A"
            LBA[Load Balancer A]
            APIA[API Cluster A]
        end
        
        subgraph "Region B"
            LBB[Load Balancer B]
            APIB[API Cluster B]
        end
        
        subgraph "Global Data"
            Neo4jHA[(Neo4j Causal Cluster)]
            RedisHA[(Redis Sentinel)]
        end
        
        CDN --> WAF
        WAF --> LBA & LBB
        LBA --> APIA
        LBB --> APIB
        APIA & APIB --> Neo4jHA & RedisHA
    end
```

### Deployment Options

| Platform | Configuration | Best For |
|----------|--------------|----------|
| **Docker Compose** | Single YAML, all services | Development, small teams |
| **Kubernetes** | Helm charts, horizontal scaling | Production, enterprise |
| **Fly.io** | Edge deployment, global | Distributed workloads |
| **Railway** | Zero-config deployment | Rapid prototyping |
| **AWS/GCP/Azure** | Full cloud native | Enterprise scale |

---

## 8. API Architecture

```mermaid
graph TB
    subgraph "API Routes"
        Chat[/chat]
        RAGRoute[/rag]
        Memory[/memory]
        Voice[/voice]
        Admin[/admin]
        Health[/health]
    end
    
    subgraph "Middleware Stack"
        CORS[CORS]
        RateLimit[Rate Limiting]
        AuthMW[Authentication]
        Audit[Audit Logging]
        Compress[Compression]
    end
    
    subgraph "WebSocket"
        WSChat[/ws/chat]
        WSVoice[/ws/voice]
        WSStatus[/ws/status]
    end
    
    Request[📥 Request] --> CORS
    CORS --> RateLimit
    RateLimit --> AuthMW
    AuthMW --> Audit
    Audit --> Compress
    
    Compress --> Chat & RAGRoute & Memory & Voice & Admin & Health
    Compress --> WSChat & WSVoice & WSStatus
```

### Endpoints Overview

| Endpoint | Method | Description |
|----------|--------|-------------|
| `/chat` | POST | Main chat interface with streaming |
| `/rag/query` | POST | Direct RAG queries |
| `/rag/ingest` | POST | Ingest documents |
| `/memory/search` | POST | Search memory |
| `/voice/synthesize` | POST | Text-to-speech |
| `/admin/modes` | GET/PUT | Mode configuration |
| `/health` | GET | Health checks |
| `/ws/chat` | WebSocket | Real-time chat |

---

## 9. Memory System

```mermaid
graph TB
    subgraph "Memory Types"
        Working[🧠 Working Memory<br/>Current session context]
        Episodic[📅 Episodic Memory<br/>Past conversations]
        Semantic[📚 Semantic Memory<br/>Facts and knowledge]
        Procedural[⚙️ Procedural Memory<br/>Skills and patterns]
    end
    
    subgraph "Storage"
        Redis[(Redis<br/>Hot cache)]
        Neo4j[(Neo4j<br/>Long-term graph)]
        Vector[(Vector DB<br/>Embeddings)]
    end
    
    subgraph "Operations"
        Store[💾 Store]
        Recall[🔍 Recall]
        Forget[🗑️ Forget]
        Summarize[📝 Summarize]
    end
    
    Working --> Redis
    Episodic --> Neo4j
    Semantic --> Neo4j
    Procedural --> Neo4j
    
    Episodic --> Vector
    Semantic --> Vector
    
    Store --> Working & Episodic & Semantic & Procedural
    Recall --> Working & Episodic & Semantic & Procedural
    Forget --> Episodic
    Summarize --> Episodic
```

### Memory Node Schema (Neo4j)

```cypher
// Memory node
(:Memory {
    id: string,
    content: string,
    embedding: list<float>,
    timestamp: datetime,
    type: "episodic" | "semantic" | "procedural",
    importance: float,
    access_count: int,
    last_accessed: datetime
})

// Relationships
(:Memory)-[:FOLLOWS]->(:Memory)
(:Memory)-[:REFERENCES]->(:Entity)
(:Memory)-[:PART_OF]->(:Session)
```

---

## 10. Technology Stack

```mermaid
mindmap
    root((Agentic Brain))
        Core
            Python 3.11+
            FastAPI
            Pydantic
            asyncio
        AI/ML
            sentence-transformers
            MLX Apple Silicon
            PyTorch CUDA
            LangChain
        Storage
            Neo4j
            Redis
            PostgreSQL
            Vector DBs
        LLM Providers
            OpenAI
            Anthropic
            Groq
            Ollama
            Azure
            Together
        Infrastructure
            Docker
            Kubernetes
            Kafka/Redpanda
            Temporal
        Observability
            Prometheus
            OpenTelemetry
            Structured Logging
        Security
            JWT/OAuth2
            SAML
            mTLS
            AES-256
```

### Key Dependencies

| Category | Technology | Purpose |
|----------|------------|---------|
| **Web Framework** | FastAPI | Async HTTP/WebSocket server |
| **Validation** | Pydantic | Data validation and serialization |
| **Graph Database** | Neo4j | Knowledge graph and memory |
| **Cache** | Redis | Session cache and rate limiting |
| **Embeddings** | sentence-transformers | Vector embeddings |
| **Streaming** | Kafka/Redpanda | Event streaming |
| **Workflow** | Temporal | Durable workflows |
| **Monitoring** | Prometheus | Metrics collection |
| **Tracing** | OpenTelemetry | Distributed tracing |

---

## Quick Reference

### Environment Variables

```bash
# Core
AGENTIC_BRAIN_MODE=professional
AGENTIC_BRAIN_LOG_LEVEL=info

# LLM Providers
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
GROQ_API_KEY=gsk_...

# Storage
NEO4J_URI=bolt://localhost:7687
REDIS_URL=redis://localhost:6379

# Security
JWT_SECRET=your-secret-key
API_KEY_SALT=your-salt
```

### CLI Commands

```bash
# Start server
agentic-brain serve --mode professional

# Check health
agentic-brain health

# Switch mode
agentic-brain mode set enterprise

# Run RAG query
agentic-brain rag query "How do I deploy?"
```

---

## Further Reading

- [RAG Pipeline Guide](../RAG.md)
- [Security Documentation](../SECURITY.md)
- [LLM Provider Guide](../LLM_PROVIDERS.md)
- [Memory System](../MEMORY.md)
- [Voice Integration](../VOICE_INTEGRATION_GUIDE.md)
- [Deployment Guide](../DEPLOYMENT.md)

---

<div align="center">

**Built with 💜 by Agentic Brain Contributors**

*Part of the Brain ecosystem*

</div>
