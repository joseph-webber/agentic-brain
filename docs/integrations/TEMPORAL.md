# 🚀 Temporal.io Integration

> **Durable Execution for AI Agents That Never Give Up**

Temporal.io is the industry-leading durable execution platform, and Agentic Brain brings its battle-tested patterns to AI workflows. When your agent is processing a complex task and the server crashes? No problem. It picks up exactly where it left off.

---

## 🎯 What Temporal.io Brings

### The Problem: AI Workflows Are Fragile

Traditional AI pipelines fail completely on:
- **Network timeouts** during LLM calls
- **Rate limits** from API providers
- **Server restarts** mid-workflow
- **Long-running tasks** that exceed connection limits

Lost work. Lost money. Lost trust.

### The Solution: Durable Execution

Temporal.io's approach records every step as an **immutable event**. If anything fails, replay events to restore state and continue from the last successful step.

| Feature | What It Does | Why It Matters |
|---------|--------------|----------------|
| **Event Sourcing** | Records every state change | Perfect audit trail, time travel debugging |
| **Replay Recovery** | Rebuilds state from events | Zero data loss on crash |
| **Distributed Queues** | Scales across workers | Handle 1000s of concurrent agents |
| **Signals** | External input to workflows | Human-in-the-loop approvals |
| **Queries** | Read-only state inspection | Monitor progress without affecting execution |
| **Retries** | Automatic with backoff | Handle rate limits, transient failures |
| **Versioning** | Safe workflow updates | Deploy new code without breaking running workflows |

---

## 🧠 How Agentic Brain Integrates

We've built a **Temporal-compatible durability layer** in pure Python, optimized for AI workloads:

```
agentic-brain/src/agentic_brain/durability/
├── __init__.py          # Public API
├── events.py            # Event types and sourcing
├── event_store.py       # Persistent event storage (Redpanda/Kafka)
├── checkpoints.py       # Snapshot state for fast recovery
├── workflow.py          # @workflow decorator
├── activity.py          # @activity decorator
├── signals.py           # External workflow input
├── queries.py           # Read-only state inspection
├── retry_policies.py    # LLM-optimized retry strategies
├── task_queues.py       # Distributed work queues
├── worker_pool.py       # Scalable worker management
├── heartbeats.py        # Detect hung activities
├── versioning.py        # Safe workflow updates
├── dashboard.py         # FastAPI monitoring routes
└── recovery.py          # Automatic crash recovery
```

### Key Design Decisions

1. **Python-Native**: No Java dependency, pure async Python
2. **LLM-Aware**: Pre-built retry policies for rate limits, timeouts
3. **RAG Integration**: Durable retrieval pipelines
4. **Neo4j Compatible**: Events stored in graph for relationship queries

---

## 💡 Example Workflows

### Basic Durable Agent

```python
from agentic_brain.durability import (
    DurableWorkflow,
    workflow,
    activity,
    LLM_RETRY_POLICY,
)

@activity(name="analyze_document", retry_policy=LLM_RETRY_POLICY)
async def analyze_document(doc_id: str) -> dict:
    """This activity can be retried on failure."""
    # If LLM rate limited, automatic exponential backoff
    result = await llm.analyze(doc_id)
    return {"analysis": result}

@activity(name="store_results")
async def store_results(analysis: dict) -> str:
    """Store to Neo4j - also durable."""
    node_id = await neo4j.create_node("Analysis", analysis)
    return node_id

@workflow(name="document-analysis")
class DocumentAnalysisWorkflow(DurableWorkflow):
    """This workflow survives server crashes."""
    
    async def run(self, doc_ids: list[str]) -> dict:
        results = []
        
        for doc_id in doc_ids:
            # Each activity call is recorded
            # If we crash here, we resume from last completed
            analysis = await self.execute_activity(
                "analyze_document",
                args={"doc_id": doc_id}
            )
            
            node_id = await self.execute_activity(
                "store_results",
                args={"analysis": analysis}
            )
            results.append(node_id)
        
        return {"status": "complete", "nodes": results}

# Start the workflow
wf = DocumentAnalysisWorkflow()
result = await wf.start(args={"doc_ids": ["doc1", "doc2", "doc3"]})
```

### Human-in-the-Loop Approval

```python
from agentic_brain.durability import (
    DurableWorkflow,
    workflow,
    signal_handler,
    APPROVAL_SIGNAL,
)

@workflow(name="content-approval")
class ContentApprovalWorkflow(DurableWorkflow):
    """Wait for human approval before publishing."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.approved = None
        self.reviewer_notes = ""
    
    @signal_handler("approval")
    async def handle_approval(self, payload: dict):
        self.approved = payload.get("approved", False)
        self.reviewer_notes = payload.get("notes", "")
    
    async def run(self, content: dict) -> dict:
        # Generate content with AI
        draft = await self.execute_activity(
            "generate_content",
            args={"topic": content["topic"]}
        )
        
        # Wait for human approval (up to 24 hours)
        # This wait is DURABLE - survives restarts!
        await self.wait_for_signal("approval", timeout=86400)
        
        if self.approved:
            await self.execute_activity(
                "publish_content",
                args={"content": draft}
            )
            return {"status": "published", "notes": self.reviewer_notes}
        else:
            return {"status": "rejected", "notes": self.reviewer_notes}

# Send approval from anywhere (web UI, API, CLI)
from agentic_brain.durability import get_signal_dispatcher

dispatcher = get_signal_dispatcher()
await dispatcher.send_signal(
    workflow_id="content-approval-123",
    signal_name="approval",
    payload={"approved": True, "notes": "Looks great!"}
)
```

### Long-Running Research Agent

```python
from agentic_brain.durability import (
    DurableWorkflow,
    workflow,
    query_handler,
)
from datetime import timedelta

@workflow(name="research-agent")
class ResearchAgentWorkflow(DurableWorkflow):
    """Multi-day research task with progress tracking."""
    
    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.sources_searched = 0
        self.total_sources = 0
        self.findings = []
    
    @query_handler("get_progress")
    def get_progress(self) -> dict:
        """Query progress without affecting execution."""
        return {
            "sources_searched": self.sources_searched,
            "total_sources": self.total_sources,
            "findings_count": len(self.findings),
            "percent_complete": (
                self.sources_searched / self.total_sources * 100
                if self.total_sources > 0 else 0
            ),
        }
    
    async def run(self, topic: str, sources: list[str]) -> dict:
        self.total_sources = len(sources)
        
        for source in sources:
            # Search each source (may take hours)
            result = await self.execute_activity(
                "search_source",
                args={"source": source, "topic": topic},
                timeout=timedelta(hours=1),
            )
            
            if result["relevant"]:
                self.findings.append(result)
            
            self.sources_searched += 1
            
            # Durable sleep - survives restart!
            await self.sleep(timedelta(minutes=5))
        
        # Synthesize findings
        report = await self.execute_activity(
            "synthesize_report",
            args={"findings": self.findings}
        )
        
        return {"status": "complete", "report": report}
```

---

## ⚡ Pre-Built Retry Policies

We ship LLM-optimized retry policies:

| Policy | Use Case | Config |
|--------|----------|--------|
| `LLM_RETRY_POLICY` | LLM API calls | 5 attempts, handles 429/503, exponential backoff |
| `RAG_RETRY_POLICY` | Vector search | 3 attempts, handles connection errors |
| `DB_RETRY_POLICY` | Neo4j operations | 3 attempts, connection pool aware |
| `API_RETRY_POLICY` | External APIs | 4 attempts, respects Retry-After header |
| `AGGRESSIVE_RETRY_POLICY` | Critical tasks | 10 attempts, fast initial retry |
| `CONSERVATIVE_RETRY_POLICY` | Rate-limited APIs | 3 attempts, slow backoff to avoid bans |

```python
from agentic_brain.durability import LLM_RETRY_POLICY, with_retry

@with_retry(LLM_RETRY_POLICY)
async def call_openai(prompt: str) -> str:
    """Automatically retries on rate limits."""
    return await openai.chat(prompt)
```

---

## 📊 Dashboard & Monitoring

FastAPI routes for workflow visibility:

```python
from fastapi import FastAPI
from agentic_brain.durability import create_dashboard_routes

app = FastAPI()
app.include_router(create_dashboard_routes())

# Now available:
# GET  /api/workflows/           - List all workflows
# GET  /api/workflows/{id}       - Get workflow details
# GET  /api/workflows/stats      - Statistics (running, failed, etc.)
# POST /api/workflows/{id}/signal - Send signal
# POST /api/workflows/{id}/cancel - Cancel workflow
```

---

## 🔥 Why This Matters

### Before (Without Durability)

```
[12:00] Start processing 1000 documents...
[14:30] 500 documents done...
[14:35] ❌ SERVER CRASHED
[14:36] Restart...
[14:36] Start processing 1000 documents... 😭
```

### After (With Agentic Brain Durability)

```
[12:00] Start processing 1000 documents...
[14:30] 500 documents done...
[14:35] ❌ SERVER CRASHED
[14:36] Restart...
[14:36] Recovering workflow document-processing-123...
[14:36] Replaying 500 completed events...
[14:36] ✅ Resuming from document 501 😎
[16:30] All 1000 documents complete!
```

### Real-World Impact

| Scenario | Without Durability | With Durability |
|----------|-------------------|-----------------|
| 4-hour analysis job crashes at 3h | Restart from zero (4h lost) | Resume in seconds |
| LLM rate limited mid-batch | Manual retry needed | Automatic backoff & resume |
| Need to deploy code update | Wait for all workflows to finish | Hot-swap with versioning |
| Debug failed workflow | Hope logs exist | Replay exact sequence |
| Scale to 10x load | Rewrite everything | Add more workers |

---

## 🚀 Getting Started

```python
from agentic_brain.durability import (
    # Core workflow primitives
    DurableWorkflow,
    workflow,
    activity,
    
    # External input/output
    signal_handler,
    query_handler,
    
    # Recovery
    recover_workflow,
    recover_all_workflows,
    
    # Pre-built policies
    LLM_RETRY_POLICY,
    RAG_RETRY_POLICY,
    
    # Dashboard
    create_dashboard_routes,
)

# Your AI workflows now survive anything!
```

---

## 📚 Resources

- [Durability API Reference](../DURABILITY.md)
- [Temporal.io Concepts](https://docs.temporal.io/concepts)
- [Event Sourcing Patterns](https://martinfowler.com/eaaDev/EventSourcing.html)
- [Examples: Durable Workflows](../../examples/)

---

*Agentic Brain's durability layer: Because AI agents should be as reliable as the problems they solve.*
