# Meta AI Architecture

Agentic Brain is not just another chatbot. It is a **Meta AI**: an AI system that routes, supervises, verifies, and improves other AI systems instead of depending on a single model or a single operating mode.

In Agentic Brain, the chatbot is only the visible surface. Underneath it sits an orchestration layer that can:

- choose between local and cloud models
- adapt behavior to persona, workload, and security posture
- recover from provider or infrastructure failures
- reconfigure itself around available hardware and services
- combine memory, routing, retrieval, and monitoring into one operating system for AI work

---

## What Makes It "Meta"

### 1. Multi-LLM orchestration

Instead of binding the user experience to one provider, Agentic Brain coordinates many.

```text
User Query
    │
    ▼
┌──────────────────────────────────────────────────────────────┐
│                 UNIFIED BRAIN / META AI                     │
│                                                              │
│  Providers: Claude · OpenAI · Groq · Gemini · Together      │
│             xAI · OpenRouter · Ollama / local               │
│                                                              │
│  Core meta behaviors:                                       │
│  • task analysis                                             │
│  • smart routing                                             │
│  • fallback chains                                           │
│  • optional parallel dispatch                                │
│  • consensus / smash modes                                   │
│  • response aggregation                                      │
└──────────────────────────────────────────────────────────────┘
    │
    ▼
Best available answer for this context
```

This is the core difference between a normal chatbot and Agentic Brain:

| Traditional chatbot | Agentic Brain Meta AI |
|---|---|
| One provider | Many providers |
| One response path | Dynamic routing paths |
| One failure domain | Fallback and redundancy |
| Static behavior | Context-sensitive behavior |
| Thin memory | Graph memory + retrieval |

Implementation-aligned examples:

- `LLMRouterCore` provides alias resolution, retry/backoff, and ordered fallback routing.
- `LLMRouter` adds streaming, caches, Redis coordination, and broader provider support.
- `SmartRouter` adds worker selection, task-specific routing, and multi-worker execution modes.
- `UnifiedBrain` is the higher-level concept that turns many models into one coordinated intelligence.

Primary references:

- `docs/UNIFIED_BRAIN.md`
- `docs/LLM_ROUTING.md`
- `src/agentic_brain/llm/router.py`
- `src/agentic_brain/router/routing.py`
- `src/agentic_brain/smart_router/core.py`

### 2. Polymorphic behavior

Agentic Brain is polymorphic because the **same system changes how it behaves** based on user type, risk level, deployment posture, and persona.

It does not just answer questions differently; it can change:

- model selection
- response style
- token limits
- logging behavior
- allowed providers
- compliance posture
- whether it can use the network at all

#### Persona-level polymorphism

The project already supports persona-driven setup and generation.

| Persona / context | Resulting behavior |
|---|---|
| Beginner / minimal | simpler setup, reduced features, lower complexity |
| Technical / developer | code-focused responses, larger limits, dev-friendly defaults |
| Professional / enterprise | formal output, predictable routing, stronger controls |
| Accessibility-first | clear structure, WCAG-oriented behavior |
| Research | citation-oriented, analytical, context-heavy |

Reference: `docs/PERSONA_SETUP.md`

#### Security-posture polymorphism

`SecurityPosture` makes the same router behave differently for different operating environments.

| Posture | Behavior |
|---|---|
| `open` | broad worker access |
| `standard` | balanced defaults |
| `restricted` | only approved workers |
| `airgapped` | local-only, no external APIs |
| `compliance` | prompt/response logging, PII-aware controls |

Reference: `src/agentic_brain/smart_router/posture.py`

#### Domain-level polymorphism

The following description captures the design intent well:

> "a META AI chatbot with polymorphic behaviors, self-healing, self-configuring"

The same core can therefore be framed for different environments:

| Context | Expected behavior |
|---|---|
| Beginner user | guided, simple, low-friction |
| Developer | technical, code-first, tool-heavy |
| Enterprise | audited, restricted, policy-aware |
| Defense / airlocked | local-only, isolated, no-network posture |
| Medical / regulated | careful, provenance-aware, logging/compliance enabled |

This adaptability is what makes Agentic Brain a platform, not just an assistant.

### 3. Self-healing

A Meta AI must continue operating even when pieces fail. Agentic Brain includes multiple recovery layers.

#### Routing-level self-healing

At the model layer, failures do not automatically end the conversation.

- rate-limit responses are treated as retryable
- transient HTTP failures are retried with backoff
- fallback chains move to the next viable model
- local-first routing reduces dependence on any single vendor

Examples from the current stack:

- `LLMRouterCore.RETRYABLE_STATUS_CODES` includes `429`, `500`, `502`, `503`, and `504`
- `LLMRouter.FALLBACK_CHAIN` defines ordered provider/model failover
- `SmartRouter` spreads requests across multiple workers for speed and resilience

#### Infrastructure-level self-healing

At the service layer, infrastructure monitoring is explicit.

`HealthMonitor` in `src/agentic_brain/infra/health_monitor.py`:

- monitors Redis, Neo4j, and Redpanda
- tracks service health state and response time
- can auto-restart unhealthy services
- exposes health information for operational visibility

`BotHealth` in `src/agentic_brain/bots/health.py`:

- checks Neo4j and Ollama availability
- records run history and service health
- provides a lightweight operational view for agents and bots

#### Recovery patterns

| Failure | Meta AI response |
|---|---|
| LLM unavailable | route to the next provider |
| Rate limited | retry, back off, or cascade |
| Ollama not running | use configured cloud provider if allowed |
| Cloud unavailable | stay local where possible |
| Redis / Neo4j / Redpanda degraded | health monitoring detects and can restart |
| Long-running workflow interrupted | durable graph state can support recovery and replay |

Self-healing in Agentic Brain is therefore not a single feature. It is the combined effect of router failover, worker diversity, health monitoring, and durable graph-backed state.

### 4. Self-configuring

A Meta AI should not require the operator to hand-tune every environment. Agentic Brain already contains several self-configuring patterns.

#### Provider detection

`ProviderChecker` detects what is actually available:

- checks whether Ollama is installed and running
- checks which API keys are present
- reports why a provider is or is not usable

Reference: `src/agentic_brain/router/provider_checker.py`

#### Persona-driven generation

The installer and ADL flow derive configuration from persona selection:

- persona selects defaults
- ADL generates config artifacts
- routing, voice, and deployment defaults follow from that persona

Reference: `docs/PERSONA_SETUP.md`

#### Hardware-aware retrieval and embeddings

The GraphRAG stack is designed to use accelerated embeddings when available:

- MLX-backed embeddings on Apple Silicon when available
- deterministic fallback embeddings when acceleration is unavailable
- Neo4j vector search for graph-native retrieval

Reference: `docs/GRAPHRAG.md`

#### Posture-aware execution

The same prompt can execute differently based on operating posture:

- free-worker preference for cost control
- local-only routing in airgapped mode
- compliance logging in regulated mode
- allow/block lists for provider restriction

In practice, self-configuration means Agentic Brain tries to fit the environment instead of forcing the environment to fit the assistant.

---

## Architecture Layers

Agentic Brain becomes a Meta AI by stacking multiple control layers on top of the chat experience.

### Layer 1: Transport — how you connect

This is the interface surface where humans, apps, and devices enter the system.

Supported or documented interaction patterns include:

- terminal / CLI
- REST API
- Server-Sent Events streaming
- WebSocket real-time chat
- Python client integrations
- voice-oriented interfaces

Reference starting points:

- `docs/API.md`
- `docs/WEBSOCKET_API.md`
- `docs/VOICE_ARCHITECTURE.md`

### Layer 2: Intelligence — how it thinks

This is the meta layer that decides **which intelligence to use and how**.

Core capabilities:

- task analysis
- model alias resolution
- smart provider routing
- local-first operation
- task-specific chains such as fast, code, and reasoning
- worker orchestration through `SmartRouter`
- consensus or smash-style aggregation for higher-confidence answers

```text
Prompt
  ↓
Classify task
  ↓
Select posture + persona + route
  ↓
Choose one or more workers
  ↓
Run, retry, or cascade
  ↓
Aggregate final response
```

### Layer 3: Memory — how it remembers

A Meta AI cannot stay meta if every request is stateless. Agentic Brain uses Neo4j as durable memory and retrieval infrastructure.

Neo4j supports:

1. GraphRAG retrieval
2. conversation memory
3. workflow durability
4. topic and community overlays

Graph memory capabilities include:

- documents, chunks, and entities
- relationship persistence
- session and message history
- summaries for memory compaction
- hybrid vector + graph retrieval
- community analysis such as Leiden/Louvain-compatible workflows

References:

- `docs/NEO4J_ARCHITECTURE.md`
- `docs/GRAPHRAG.md`
- `docs/MEMORY.md`

### Layer 4: Self-management — how it heals and governs itself

This layer is what elevates Agentic Brain from orchestration to **Meta AI operations**.

It includes:

- provider availability checks
- health monitoring
- auto-restart behavior
- compliance posture enforcement
- cost-aware worker preference
- caching to reduce repeated spend
- operational metrics and status tracking

Without this layer, multi-LLM orchestration is just a feature. With this layer, it becomes a self-managing AI system.

---

## End-to-End Meta AI Flow

```text
User / App / Voice
        │
        ▼
Transport Layer
CLI · REST · WS · SSE · Voice
        │
        ▼
Meta Control Layer
persona + posture + provider detection
        │
        ▼
Intelligence Layer
router core + full router + smart router
        │
        ├──────────────┬──────────────┬──────────────┐
        ▼              ▼              ▼              ▼
     Claude         OpenAI          Groq          Ollama
        │              │              │              │
        └──────────────┴───────┬──────┴──────────────┘
                               ▼
                     response selection / consensus
                               │
                               ▼
                    Memory + GraphRAG augmentation
                               │
                               ▼
                    final answer + durable state write
                               │
                               ▼
                      health, metrics, recovery loop
```

---

## Deployment Patterns

Agentic Brain can be described as a Meta AI across several deployment styles.

### Pattern 1: Zero-config / beginner path

```bash
pip install agentic-brain
agentic chat
```

Best for:

- evaluation
- solo developers
- local experimentation

Meta AI value:

- minimal setup
- automatic provider detection
- simple entry into a multi-LLM system

### Pattern 2: Docker / standard path

```bash
docker-compose up -d
```

Best for:

- local teams
- repeatable environments
- running app + infrastructure together

Meta AI value:

- repeatable infrastructure
- easier health monitoring
- consistent Redis / Neo4j / API startup

### Pattern 3: Enterprise orchestration

For enterprise, the architectural pattern is container orchestration with readiness, liveness, and policy controls.

```bash
kubectl apply -f <your-manifests>
```

If your environment packages Agentic Brain as a Helm chart, the equivalent pattern is:

```bash
helm install agentic-brain <your-chart>
```

Best for:

- regulated operations
- autoscaling APIs
- policy-driven deployments

Meta AI value:

- controlled rollout
- isolated services
- stronger observability and recovery

### Pattern 4: Airlocked / defense posture

```python
from agentic_brain.smart_router.posture import get_posture

posture = get_posture("airgapped")  # local-only workers
```

Best for:

- classified or disconnected networks
- strict data residency
- local-only inference

Meta AI value:

- local-worker enforcement
- no external API dependency
- posture-driven execution constraints

Note: this mode is already represented by `SecurityPosture(mode=AIRGAPPED)`, which restricts execution to the local worker.

---

## Why "Meta AI" Matters

### Traditional chatbot model

- one model
- one control surface
- one memory model, if any
- brittle when providers fail
- hard to adapt to new environments

### Agentic Brain Meta AI model

- many models
- one orchestration layer
- posture-aware execution
- durable graph memory
- built-in recovery paths
- environment-aware configuration

The result is a system designed to be:

- **faster** through fast routes, local-first options, and layered responses
- **smarter** through model specialization and optional multi-worker collaboration
- **safer** through consensus, postures, and graph-backed context
- **more resilient** through fallback chains, health checks, and restartable infrastructure

This is why Agentic Brain should be described as a **Meta AI chatbot**:

> it does not merely generate answers  
> it governs the system that generates answers

---

## Implementation Map

| Capability | Current implementation anchor |
|---|---|
| lightweight fallback routing | `src/agentic_brain/llm/router.py` |
| production multi-provider routing | `src/agentic_brain/router/routing.py` |
| worker orchestration / smash modes | `src/agentic_brain/smart_router/core.py` |
| security posture / airgapped mode | `src/agentic_brain/smart_router/posture.py` |
| provider discovery | `src/agentic_brain/router/provider_checker.py` |
| infra self-healing | `src/agentic_brain/infra/health_monitor.py` |
| bot health checks | `src/agentic_brain/bots/health.py` |
| graph memory and workflow durability | `docs/NEO4J_ARCHITECTURE.md` |
| GraphRAG and community retrieval | `docs/GRAPHRAG.md` |
| persona-driven polymorphism | `docs/PERSONA_SETUP.md` |

---

## One-Sentence Definition

**Agentic Brain is a Meta AI system: a polymorphic, multi-LLM, graph-memory-driven chatbot that can route, verify, recover, and reconfigure itself across different environments and trust boundaries.**
