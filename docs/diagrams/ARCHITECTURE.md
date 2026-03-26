# 🧠 Agentic Brain Architecture Diagrams

> Professional architecture documentation for enterprise evaluation

---

## 📐 System Overview

High-level view of the Agentic Brain architecture showing all major components and their interactions.

```mermaid
flowchart TB
    subgraph Clients["🖥️ Client Layer"]
        CLI["CLI<br/>ab chat"]
        SDK["Python SDK<br/>import agentic_brain"]
        API["REST API<br/>FastAPI"]
        WS["WebSocket<br/>Real-time"]
    end

    subgraph Core["🧠 Agentic Brain Core"]
        direction TB
        
        subgraph LLM["🤖 LLM Router"]
            Ollama["🦙 Ollama<br/>Local"]
            Anthropic["🎭 Anthropic<br/>Claude"]
            OpenAI["🧠 OpenAI<br/>GPT-4"]
            OpenRouter["🌐 OpenRouter<br/>100+ Models"]
            Azure["🔷 Azure<br/>OpenAI"]
            Bedrock["☁️ AWS<br/>Bedrock"]
            Cohere["🌊 Cohere"]
            HuggingFace["🤗 HuggingFace"]
        end

        subgraph RAG["📚 RAG/GraphRAG Engine"]
            Loaders["54 Data Loaders"]
            Chunker["Semantic Chunker"]
            Embedder["Hardware-Accelerated<br/>Embeddings"]
            VectorStore["Vector Store"]
            GraphRAG["GraphRAG<br/>Knowledge Graph"]
            Retriever["Hybrid Retriever<br/>Vector + BM25"]
            Reranker["Cross-Encoder<br/>Reranker"]
        end

        subgraph Durability["⏱️ Durability Engine"]
            Workflows["Workflow Runtime<br/>Temporal Compatible"]
            Activities["Activity Workers"]
            Signals["Signals & Queries"]
            Sagas["Saga Compensation"]
            Versioning["Workflow Versioning"]
        end

        subgraph ModeSystem["🎯 Mode Manager"]
            ModeConfig["42 Deployment Modes"]
            Compliance["Compliance Engine"]
            Isolation["Data Isolation"]
        end
    end

    subgraph Storage["💾 Persistence Layer"]
        Neo4j["🔵 Neo4j<br/>Knowledge Graph"]
        Firebase["🔥 Firebase<br/>Real-time Sync"]
        Postgres["🐘 PostgreSQL<br/>Structured Data"]
        Redis["🔴 Redis<br/>Cache & Sessions"]
        S3["📦 S3/MinIO<br/>Object Storage"]
    end

    subgraph Security["🔒 Security Layer"]
        Auth["Enterprise Auth<br/>JWT/OAuth/SAML"]
        Secrets["Secrets Manager<br/>Vault/AWS SM/Keychain"]
        Audit["Audit Logging"]
        Encryption["Encryption<br/>At Rest & In Transit"]
    end

    subgraph Observability["📊 Observability"]
        Metrics["Prometheus<br/>Metrics"]
        Traces["OpenTelemetry<br/>Tracing"]
        Dashboard["Real-time<br/>Dashboard"]
    end

    CLI --> Core
    SDK --> Core
    API --> Core
    WS --> Core

    Core --> Storage
    Core --> Security
    Core --> Observability

    LLM --> RAG
    RAG --> Durability
    Durability --> ModeSystem

    Neo4j --> GraphRAG
    VectorStore --> Retriever

    classDef client fill:#e1f5fe,stroke:#01579b
    classDef core fill:#fff3e0,stroke:#e65100
    classDef storage fill:#f3e5f5,stroke:#7b1fa2
    classDef security fill:#ffebee,stroke:#c62828
    classDef observe fill:#e8f5e9,stroke:#2e7d32

    class CLI,SDK,API,WS client
    class LLM,RAG,Durability,ModeSystem core
    class Neo4j,Firebase,Postgres,Redis,S3 storage
    class Auth,Secrets,Audit,Encryption security
    class Metrics,Traces,Dashboard observe
```

---

## 📊 RAG Pipeline Architecture

Detailed view of how data flows through the RAG (Retrieval Augmented Generation) system.

```mermaid
flowchart LR
    subgraph Sources["📥 Data Sources (54 Loaders)"]
        direction TB
        S1["📁 Files<br/>PDF, DOCX, MD, TXT"]
        S2["☁️ Cloud<br/>Drive, SharePoint, S3"]
        S3["💬 Comms<br/>Slack, Teams, Discord"]
        S4["🎫 CRM<br/>Salesforce, HubSpot"]
        S5["🔧 Dev<br/>GitHub, Jira, Notion"]
        S6["💰 Finance<br/>Stripe, Xero, QB"]
    end

    subgraph Processing["⚙️ Processing Pipeline"]
        direction TB
        P1["📄 Document Parsing<br/>Extract text & metadata"]
        P2["✂️ Semantic Chunking<br/>Context-aware splitting"]
        P3["🔗 Entity Extraction<br/>NER + Relationship"]
        P4["📐 Embedding Generation<br/>M1/M2/CUDA accelerated"]
    end

    subgraph Storage["💾 Dual Storage"]
        direction TB
        V1["🔢 Vector Index<br/>HNSW / IVF"]
        G1["🕸️ Knowledge Graph<br/>Neo4j GraphRAG"]
    end

    subgraph Retrieval["🔍 Hybrid Retrieval"]
        direction TB
        R1["📊 Vector Search<br/>Semantic similarity"]
        R2["📝 BM25 Keyword<br/>Term matching"]
        R3["🕸️ Graph Traversal<br/>Relationship paths"]
        R4["🎯 Reciprocal Rank Fusion<br/>Score combination"]
    end

    subgraph Ranking["⭐ Reranking"]
        direction TB
        RR1["🔬 Cross-Encoder<br/>Pairwise scoring"]
        RR2["📍 Citation Mapping<br/>Source tracking"]
        RR3["📈 Confidence Scoring<br/>0.0 - 1.0"]
    end

    subgraph Generation["🤖 LLM Generation"]
        direction TB
        L1["📋 Prompt Assembly<br/>Context + Query"]
        L2["🧠 LLM Inference<br/>8 Providers"]
        L3["✅ Response + Citations<br/>Grounded output"]
    end

    Sources --> P1
    P1 --> P2
    P2 --> P3
    P3 --> P4

    P4 --> V1
    P3 --> G1

    V1 --> R1
    G1 --> R3
    R1 --> R4
    R2 --> R4
    R3 --> R4

    R4 --> RR1
    RR1 --> RR2
    RR2 --> RR3

    RR3 --> L1
    L1 --> L2
    L2 --> L3

    style Sources fill:#e3f2fd
    style Processing fill:#fff8e1
    style Storage fill:#f3e5f5
    style Retrieval fill:#e8f5e9
    style Ranking fill:#fff3e0
    style Generation fill:#fce4ec
```

---

## 🎯 Mode System Hierarchy

The 42 deployment modes organized by category, showing inheritance and specialization.

```mermaid
flowchart TB
    subgraph Base["🏗️ Base Layer"]
        BaseMode["BaseMode<br/>Core functionality"]
    end

    subgraph User["👤 User Modes (8)"]
        direction LR
        Home["🏠 home<br/>Family safe"]
        Dev["💻 dev<br/>Debug mode"]
        Ops["🔧 ops<br/>DevOps"]
        Sec["🔐 sec<br/>Security"]
        Creator["🎨 creator<br/>Content"]
        Influencer["📱 influencer<br/>Social"]
        Streamer["📺 streamer<br/>Live"]
        Writer["✍️ writer<br/>Long-form"]
    end

    subgraph Industry["🏭 Industry Modes (20)"]
        direction TB
        
        subgraph Healthcare["Healthcare"]
            Med["🏥 medical"]
            Pha["💊 pharma"]
            Bio["🧬 biotech"]
        end
        
        subgraph Finance["Finance"]
            Fin["🏦 banking"]
            Ins["📋 insurance"]
        end
        
        subgraph Government["Government"]
            Gov["🏛️ government"]
            Mil["⚔️ military"]
        end
        
        subgraph Care["Care Services"]
            Age["👴 aged-care"]
            Dis["♿ disability"]
        end
        
        subgraph Other["Other Industries"]
            Ret["🛒 retail"]
            Edu["🎓 education"]
            Leg["⚖️ legal"]
            Man["🏭 manufacturing"]
            Log["📦 logistics"]
            Hos["🏨 hospitality"]
            Rea["🏠 real-estate"]
            Ene["⚡ energy"]
            Tel["📡 telecom"]
            Media["📺 media"]
        end
    end

    subgraph Architecture["🏗️ Architecture Modes (8)"]
        direction LR
        Mono["📦 monolith"]
        Micro["🔷 microservices"]
        Event["📨 event-driven"]
        Lambda["⚡ serverless"]
        Edge["🌐 edge"]
        Hybrid["🔀 hybrid"]
        JHip["🅹 jhipster"]
        Temp["⏱️ temporal"]
    end

    subgraph Compliance["📜 Compliance Modes (4)"]
        direction LR
        HIPAA["🏥 HIPAA"]
        PCI["💳 PCI-DSS"]
        SOC2["🔒 SOC 2"]
        FedRAMP["🇺🇸 FedRAMP"]
    end

    subgraph Power["⚡ Power Modes (2)"]
        direction LR
        Perf["🚀 performance<br/>Max throughput"]
        Safe["🛡️ safe<br/>Max validation"]
    end

    BaseMode --> User
    BaseMode --> Industry
    BaseMode --> Architecture
    BaseMode --> Compliance
    BaseMode --> Power

    Med --> HIPAA
    Fin --> PCI
    Gov --> FedRAMP
    Mil --> FedRAMP

    classDef base fill:#e0e0e0,stroke:#616161
    classDef user fill:#bbdefb,stroke:#1976d2
    classDef industry fill:#c8e6c9,stroke:#388e3c
    classDef arch fill:#fff9c4,stroke:#fbc02d
    classDef compliance fill:#ffcdd2,stroke:#d32f2f
    classDef power fill:#e1bee7,stroke:#7b1fa2

    class BaseMode base
    class Home,Dev,Ops,Sec,Creator,Influencer,Streamer,Writer user
    class Med,Pha,Bio,Fin,Ins,Gov,Mil,Age,Dis,Ret,Edu,Leg,Man,Log,Hos,Rea,Ene,Tel,Media industry
    class Mono,Micro,Event,Lambda,Edge,Hybrid,JHip,Temp arch
    class HIPAA,PCI,SOC2,FedRAMP compliance
    class Perf,Safe power
```

---

## 🚀 Deployment Architecture

Shows the various deployment options from local development to cloud-native Kubernetes.

```mermaid
flowchart TB
    subgraph Local["🖥️ Local Development"]
        direction TB
        L1["pip install agentic-brain"]
        L2["ab chat"]
        L3["Ollama + Neo4j Desktop"]
    end

    subgraph Docker["🐳 Docker Compose"]
        direction TB
        D1["docker-compose up"]
        D2["All services containerized"]
        D3["Neo4j + Redis + API"]
    end

    subgraph K8s["☸️ Kubernetes"]
        direction TB
        
        subgraph Ingress["🌐 Ingress"]
            IG["Nginx/Traefik<br/>TLS Termination"]
        end
        
        subgraph Services["🔷 Services"]
            API_SVC["API Service<br/>ClusterIP"]
            WS_SVC["WebSocket Service<br/>ClusterIP"]
        end
        
        subgraph Workloads["📦 Workloads"]
            API_DEP["API Deployment<br/>3 replicas"]
            WORKER_DEP["Worker Deployment<br/>5 replicas"]
            EMBED_DEP["Embedding Service<br/>GPU nodes"]
        end
        
        subgraph StatefulSets["💾 StatefulSets"]
            NEO4J_SS["Neo4j Cluster<br/>3 nodes"]
            REDIS_SS["Redis Cluster<br/>3 nodes"]
        end
        
        subgraph Config["⚙️ Config"]
            CM["ConfigMaps"]
            SEC["Secrets"]
            HPA["HorizontalPodAutoscaler"]
        end
    end

    subgraph Cloud["☁️ Cloud Native"]
        direction TB
        
        subgraph AWS["AWS"]
            EKS["EKS Cluster"]
            RDS["RDS PostgreSQL"]
            ELASTIC["ElastiCache Redis"]
            SM["Secrets Manager"]
        end
        
        subgraph GCP["Google Cloud"]
            GKE["GKE Cluster"]
            CSQL["Cloud SQL"]
            MEM["Memorystore"]
            GSM["Secret Manager"]
        end
        
        subgraph Azure["Azure"]
            AKS["AKS Cluster"]
            AZSQL["Azure Database"]
            AZCACHE["Azure Cache"]
            KV["Key Vault"]
        end
    end

    subgraph AirGap["🔒 Air-Gapped"]
        direction TB
        AG1["Offline Install Package"]
        AG2["Local Ollama Models"]
        AG3["Embedded Neo4j"]
        AG4["No External Dependencies"]
    end

    L1 --> L2
    L2 --> L3

    D1 --> D2
    D2 --> D3

    IG --> Services
    Services --> Workloads
    Workloads --> StatefulSets
    Config --> Workloads

    AWS --> EKS
    GCP --> GKE
    Azure --> AKS

    AG1 --> AG2
    AG2 --> AG3
    AG3 --> AG4

    style Local fill:#e3f2fd
    style Docker fill:#e8f5e9
    style K8s fill:#fff3e0
    style Cloud fill:#fce4ec
    style AirGap fill:#f3e5f5
```

---

## ⏱️ Durability Engine Architecture

Temporal-compatible workflow execution engine with 27 durability modules.

```mermaid
flowchart TB
    subgraph Client["📱 Client"]
        Start["Start Workflow"]
        Signal["Send Signal"]
        Query["Query State"]
    end

    subgraph Engine["⏱️ Durability Engine"]
        direction TB
        
        subgraph Runtime["🔄 Workflow Runtime"]
            WF["Workflow Executor<br/>Deterministic replay"]
            History["Event History<br/>Persistent log"]
            Timer["Timer Service<br/>Scheduled wake"]
        end
        
        subgraph Workers["👷 Activity Workers"]
            Pool["Worker Pool<br/>Concurrent execution"]
            Retry["Retry Logic<br/>Exponential backoff"]
            Timeout["Timeout Handler<br/>Heartbeat monitoring"]
        end
        
        subgraph Patterns["📐 Durability Patterns"]
            Saga["Saga<br/>Compensation"]
            ChildWF["Child Workflows<br/>Composition"]
            ContinueAs["Continue-As-New<br/>Large histories"]
            Version["Versioning<br/>Safe updates"]
        end
    end

    subgraph Persistence["💾 Persistence"]
        EventStore["Event Store<br/>Workflow history"]
        TaskQueue["Task Queues<br/>Activity dispatch"]
        Search["Search Index<br/>Workflow visibility"]
    end

    subgraph Features["✨ 27 Modules"]
        direction LR
        F1["Signals & Queries"]
        F2["Local Activities"]
        F3["Async Activities"]
        F4["Cron Schedules"]
        F5["Side Effects"]
        F6["Update Validators"]
        F7["Interceptors"]
        F8["Namespaces"]
        F9["Task Routing"]
    end

    Client --> Runtime
    Runtime --> Workers
    Workers --> Patterns
    Patterns --> Persistence
    
    Engine --> Features

    style Client fill:#e3f2fd
    style Engine fill:#fff8e1
    style Persistence fill:#f3e5f5
    style Features fill:#e8f5e9
```

---

## 🔒 Security Architecture

Enterprise security controls and compliance boundaries.

```mermaid
flowchart TB
    subgraph External["🌐 External"]
        User["👤 User"]
        Client["📱 Client App"]
    end

    subgraph Edge["🛡️ Edge Security"]
        WAF["WAF<br/>Web Application Firewall"]
        DDoS["DDoS Protection"]
        TLS["TLS 1.3<br/>mTLS optional"]
    end

    subgraph Auth["🔐 Authentication"]
        direction TB
        JWT["JWT Validation<br/>HS512/RS256"]
        OAuth["OAuth 2.0 / OIDC<br/>SSO Integration"]
        SAML["SAML 2.0<br/>Enterprise SSO"]
        LDAP["LDAP/AD<br/>Directory"]
        MFA["MFA<br/>TOTP/WebAuthn"]
    end

    subgraph Authz["🎫 Authorization"]
        RBAC["RBAC<br/>Role-Based"]
        ABAC["ABAC<br/>Attribute-Based"]
        Scopes["Data Scopes<br/>PUBLIC/PRIVATE/CUSTOMER"]
    end

    subgraph Secrets["🔑 Secrets Management"]
        Vault["HashiCorp Vault"]
        AWSSM["AWS Secrets Manager"]
        AzKV["Azure Key Vault"]
        GCPSM["GCP Secret Manager"]
        Keychain["macOS Keychain"]
    end

    subgraph DataSec["💾 Data Security"]
        EncRest["Encryption at Rest<br/>AES-256"]
        EncTransit["Encryption in Transit<br/>TLS 1.3"]
        Masking["Data Masking<br/>PII/PHI protection"]
        DLP["DLP<br/>Data Loss Prevention"]
    end

    subgraph Audit["📋 Audit & Compliance"]
        Logs["Audit Logs<br/>Immutable"]
        SIEM["SIEM Integration"]
        Reports["Compliance Reports<br/>SOC 2, HIPAA, PCI"]
    end

    User --> TLS
    Client --> TLS
    
    TLS --> WAF
    WAF --> DDoS
    DDoS --> Auth

    Auth --> Authz
    Authz --> Secrets
    
    Secrets --> DataSec
    DataSec --> Audit

    style External fill:#ffebee
    style Edge fill:#fff3e0
    style Auth fill:#e8f5e9
    style Authz fill:#e3f2fd
    style Secrets fill:#f3e5f5
    style DataSec fill:#fff8e1
    style Audit fill:#fce4ec
```

---

## 📊 Observability Stack

Comprehensive monitoring, logging, and tracing architecture.

```mermaid
flowchart LR
    subgraph Application["🧠 Agentic Brain"]
        Instrumented["Instrumented Code<br/>@traced decorators"]
        MetricsCol["Metrics Collector<br/>prometheus_client"]
        LogEmit["Structured Logging<br/>JSON format"]
    end

    subgraph Collection["📥 Collection Layer"]
        OTel["OpenTelemetry<br/>Collector"]
        Prom["Prometheus<br/>Scrape /metrics"]
        Fluentd["Fluentd/Fluent Bit<br/>Log shipping"]
    end

    subgraph Storage["💾 Storage"]
        Tempo["Grafana Tempo<br/>Trace storage"]
        PromDB["Prometheus TSDB<br/>Metrics storage"]
        Loki["Grafana Loki<br/>Log storage"]
    end

    subgraph Visualization["📊 Visualization"]
        Grafana["Grafana<br/>Unified dashboards"]
        Alerts["AlertManager<br/>PagerDuty/Slack"]
        Dashboard["Real-time Dashboard<br/>Workflow status"]
    end

    subgraph Metrics["📈 Key Metrics"]
        direction TB
        M1["🔢 Token Usage<br/>Per model, per user"]
        M2["⏱️ Latency P99<br/>API & LLM calls"]
        M3["📊 RAG Quality<br/>Retrieval precision"]
        M4["🔄 Workflow Health<br/>Success/failure rates"]
        M5["💾 Resource Usage<br/>CPU, Memory, GPU"]
    end

    Instrumented --> OTel
    MetricsCol --> Prom
    LogEmit --> Fluentd

    OTel --> Tempo
    Prom --> PromDB
    Fluentd --> Loki

    Tempo --> Grafana
    PromDB --> Grafana
    Loki --> Grafana

    Grafana --> Alerts
    Grafana --> Dashboard

    Metrics --> Grafana

    style Application fill:#e3f2fd
    style Collection fill:#fff3e0
    style Storage fill:#f3e5f5
    style Visualization fill:#e8f5e9
    style Metrics fill:#fce4ec
```

---

## 🗄️ Data Architecture

How data flows and is stored across the system.

```mermaid
flowchart TB
    subgraph Ingest["📥 Data Ingestion"]
        Loaders["54 Data Loaders<br/>Unified interface"]
        Stream["Streaming Ingest<br/>Real-time updates"]
        Batch["Batch Import<br/>Bulk operations"]
    end

    subgraph Process["⚙️ Processing"]
        Parse["Document Parsing<br/>Text extraction"]
        Chunk["Semantic Chunking<br/>Overlap handling"]
        Entity["Entity Extraction<br/>NER pipeline"]
        Embed["Embedding Generation<br/>Hardware accelerated"]
    end

    subgraph GraphStore["🕸️ Neo4j Knowledge Graph"]
        Nodes["📦 Nodes<br/>Documents, Entities, Concepts"]
        Rels["🔗 Relationships<br/>MENTIONS, PART_OF, SIMILAR_TO"]
        Props["📋 Properties<br/>content, embedding, metadata"]
        Vector["🔢 Vector Index<br/>Cosine similarity search"]
    end

    subgraph Relational["🐘 PostgreSQL"]
        Users["👤 Users & Sessions"]
        Workflows["⏱️ Workflow State"]
        Audit["📋 Audit Logs"]
        Analytics["📊 Usage Analytics"]
    end

    subgraph Cache["🔴 Redis"]
        Sessions["🔑 Session Cache"]
        Results["📦 Query Cache"]
        Queues["📨 Task Queues"]
        Realtime["⚡ Real-time State"]
    end

    subgraph Object["📦 Object Storage"]
        Documents["📄 Original Documents"]
        Models["🧠 Model Weights"]
        Backups["💾 Backups"]
    end

    Ingest --> Process
    
    Parse --> Chunk
    Chunk --> Entity
    Entity --> Embed

    Embed --> Vector
    Entity --> Nodes
    Entity --> Rels

    Nodes --> Props
    Rels --> Props

    Process --> Relational
    Process --> Cache

    Loaders --> Object

    style Ingest fill:#e3f2fd
    style Process fill:#fff8e1
    style GraphStore fill:#e8f5e9
    style Relational fill:#f3e5f5
    style Cache fill:#ffebee
    style Object fill:#fce4ec
```

---

## 🔌 API Architecture

RESTful and WebSocket API design patterns.

```mermaid
flowchart TB
    subgraph Gateway["🚪 API Gateway"]
        RateLimit["Rate Limiting<br/>Token bucket"]
        Validation["Request Validation<br/>Pydantic models"]
        Versioning["API Versioning<br/>/v1/, /v2/"]
    end

    subgraph REST["📡 REST Endpoints"]
        direction TB
        
        subgraph Chat["💬 /api/v1/chat"]
            ChatSync["POST /sync<br/>Synchronous"]
            ChatStream["POST /stream<br/>SSE streaming"]
        end
        
        subgraph RAG["📚 /api/v1/rag"]
            Ingest["POST /ingest<br/>Document upload"]
            Query["POST /query<br/>RAG retrieval"]
            Sources["GET /sources<br/>List documents"]
        end
        
        subgraph Workflow["⏱️ /api/v1/workflows"]
            WFStart["POST /<br/>Start workflow"]
            WFStatus["GET /{id}<br/>Get status"]
            WFSignal["POST /{id}/signal<br/>Send signal"]
            WFQuery["GET /{id}/query<br/>Query state"]
        end
        
        subgraph Mode["🎯 /api/v1/modes"]
            ModeList["GET /<br/>List modes"]
            ModeSwitch["POST /switch<br/>Change mode"]
            ModeStatus["GET /current<br/>Current mode"]
        end
    end

    subgraph WebSocket["🔌 WebSocket"]
        Connect["ws://host/ws<br/>Persistent connection"]
        Events["Event Stream<br/>Real-time updates"]
        Bidirectional["Bidirectional<br/>Send & receive"]
    end

    subgraph Response["📤 Response Format"]
        JSON["Standard JSON<br/>Consistent schema"]
        Error["Error Handling<br/>RFC 7807"]
        Pagination["Pagination<br/>Cursor-based"]
    end

    Gateway --> REST
    Gateway --> WebSocket

    REST --> Response
    WebSocket --> Response

    style Gateway fill:#e3f2fd
    style REST fill:#fff8e1
    style WebSocket fill:#e8f5e9
    style Response fill:#fce4ec
```

---

## Quick Reference

| Diagram | Purpose | Key Insights |
|---------|---------|--------------|
| [System Overview](#-system-overview) | High-level architecture | 8 LLM providers, 5 layers |
| [RAG Pipeline](#-rag-pipeline-architecture) | Data flow | 54 loaders → Neo4j → LLM |
| [Mode System](#-mode-system-hierarchy) | 42 modes | 5 categories, compliance inheritance |
| [Deployment](#-deployment-architecture) | Deployment options | Local → Docker → K8s → Cloud |
| [Durability](#️-durability-engine-architecture) | Workflow engine | 27 modules, Temporal compatible |
| [Security](#-security-architecture) | Enterprise security | Auth/Authz/Encryption/Audit |
| [Observability](#-observability-stack) | Monitoring | OpenTelemetry + Prometheus + Grafana |
| [Data](#️-data-architecture) | Data storage | Neo4j + PostgreSQL + Redis |
| [API](#-api-architecture) | API design | REST + WebSocket + Versioning |

---

<div align="center">

**[← Back to README](../../README.md)** · **[Integrations →](./INTEGRATIONS.md)**

*These diagrams render natively on GitHub. No external tools required.*

</div>
