# 🎯 Event Bus LLM Integration

Redpanda event bus integration for distributed LLM routing.

## Overview

This integration allows **ANY external agent or process** to use the Brain's smart LLM routing via Redpanda event bus. All the benefits of smart routing, caching, and fallback - accessible via simple Kafka messages.

## Architecture

```
┌─────────────────────┐
│  External Agent     │
│  (Python, JS, etc)  │
└─────────┬───────────┘
          │ Publish
          ↓
┌─────────────────────────────┐
│  brain.llm.request (topic)  │
└─────────┬───────────────────┘
          │
          ↓
┌─────────────────────────────┐
│  LLM Consumer (Python)      │
│  - Smart routing            │
│  - Redis caching            │
│  - Groq → Ollama → Cloud    │
└─────────┬───────────────────┘
          │
          ↓
┌──────────────────────────────┐
│  brain.llm.response (topic)  │
└──────────┬───────────────────┘
           │ Subscribe
           ↓
     ┌────────────┐
     │  Response  │
     └────────────┘
```

## Topics

| Topic | Purpose | Message Format |
|-------|---------|---------------|
| `brain.llm.request` | External agents send LLM requests | `{request_id, query, task_type, ...}` |
| `brain.llm.response` | Responses published here | `{request_id, response, provider_used, ...}` |
| `brain.llm.status` | Provider health updates | `{timestamp, provider, latency_ms, success}` |
| `brain.llm.reasoning` | Shared reasoning chains | `{request_id, step, reasoning}` |

## Quick Start

### 1. Start the Consumer

The consumer listens for requests and routes them:

```bash
# Background daemon
cd ~/brain/mcp-servers/openrouter
python3 event_bus_llm.py start &

# Or foreground (for debugging)
python3 event_bus_llm.py start
```

### 2. Send a Request

#### Python

```python
from event_bus_llm import publish_llm_request, wait_for_response

# Send request
request_id = publish_llm_request(
    query="Explain Python decorators in 2 sentences",
    task_type="simple",
    preferred_provider="groq"
)

# Wait for response
response = wait_for_response(request_id, timeout=30)
print(response["response"])
print(f"Provider: {response['provider_used']}")
print(f"Latency: {response['latency_ms']}ms")
```

#### Using MCP Tools

```bash
# From GitHub Copilot CLI or any MCP client
openrouter_event_request \
  --query "What is 2+2?" \
  --task_type simple \
  --timeout_sec 30
```

### 3. Subscribe to Responses

```python
from event_bus_llm import subscribe_responses

def handle_response(response_data):
    print(f"Got response: {response_data['response'][:100]}")
    print(f"Provider: {response_data['provider_used']}")

# Subscribe to ALL responses
subscribe_responses(handle_response)
```

## Request Message Format

```json
{
  "request_id": "uuid-string",
  "query": "Your question or prompt",
  "task_type": "simple|complex|coding|reasoning|general",
  "preferred_provider": "groq|ollama|claude|openai|any",
  "timeout_ms": 30000,
  "callback_topic": "optional.custom.response.topic",
  "context": {
    "session_id": "optional-session-id",
    "previous_messages": [],
    "metadata": {}
  },
  "timestamp": "2026-04-02T04:00:00Z"
}
```

## Response Message Format

```json
{
  "request_id": "uuid-string",
  "response": "The LLM response text...",
  "provider_used": "groq",
  "latency_ms": 150,
  "tokens_used": 100,
  "cached": false,
  "error": null,
  "reasoning_steps": [],
  "timestamp": "2026-04-02T04:00:01Z"
}
```

## Task Types

| Task Type | Description | Routes To |
|-----------|-------------|-----------|
| `simple` | Quick questions, status checks | Groq (ultra-fast) |
| `complex` | Multi-step reasoning | Groq 70B or Claude |
| `coding` | Code generation, debugging | Groq 70B or Claude |
| `reasoning` | Deep analysis | Claude or GPT |
| `general` | Default, auto-routed | Smart routing |

## Provider Preferences

| Provider | When Used | Latency | Cost |
|----------|-----------|---------|------|
| `groq` | Fast tasks, default | 100-200ms | FREE |
| `ollama` | Offline, privacy | 500-2000ms | FREE |
| `claude` | Complex reasoning | 2-5s | Paid |
| `openai` | GPT-specific needs | 1-3s | Paid |
| `any` | Auto-select best (default) | Varies | Varies |

## Smart Routing

The consumer uses the existing OpenRouter smart routing logic:

1. **Check cache** - If query seen before (1 hour TTL), return cached
2. **Check health** - Only use available providers
3. **Route by task** - Simple → Groq, Complex → Claude, etc.
4. **Cascade fallback** - Groq → Ollama → Cloud (never fails)

## Caching

Responses are cached in Redis for 1 hour:
- Cache key: `llm:response:{task_type}:{hash(query)}`
- Instant responses for repeated queries
- Reduces API costs
- Cache-aware in response: `"cached": true`

## Status Monitoring

Check system status via MCP tool:

```bash
openrouter_event_status
```

Shows:
- Kafka/Redpanda connection
- Redis cache status
- Consumer running (PID)
- Recent health updates

## Subscribing to Responses

Listen for responses for 60 seconds:

```bash
openrouter_event_subscribe --timeout_sec 60
```

Shows summary:
- Total responses
- Providers used
- Average latency
- Cache hit rate

## Multi-Agent Collaboration

Multiple agents can use the event bus simultaneously:

```python
# Agent 1: Question about API
request_1 = publish_llm_request("How do I use the JIRA API?", task_type="coding")

# Agent 2: Question about docs
request_2 = publish_llm_request("Where is the documentation?", task_type="simple")

# Both requests are processed in parallel
# Responses arrive independently on brain.llm.response
```

## Reasoning Chains

Agents can share reasoning steps via `brain.llm.reasoning` topic:

```python
# Agent publishes reasoning step
producer.send("brain.llm.reasoning", {
    "request_id": "uuid",
    "step": 1,
    "reasoning": "First, I need to check the API docs...",
    "timestamp": datetime.now().isoformat()
})

# Other agents can subscribe and see the reasoning
```

## Error Handling

If all providers fail, response includes error:

```json
{
  "request_id": "uuid",
  "response": null,
  "provider_used": null,
  "latency_ms": 5000,
  "tokens_used": 0,
  "cached": false,
  "error": "All providers failed: [groq timeout, ollama not running, claude rate limited]"
}
```

## Configuration

Environment variables:

```bash
# Kafka/Redpanda
export KAFKA_BOOTSTRAP_SERVERS="localhost:9092"

# Redis (optional, for caching)
export REDIS_HOST="localhost"
export REDIS_PORT="6379"
export REDIS_PASSWORD="BrainRedis2026"  # Or none for local
```

## Testing

Run the built-in test:

```bash
cd ~/brain/mcp-servers/openrouter
python3 event_bus_llm.py test
```

This will:
1. Start consumer in background
2. Send test request ("What is 2+2?")
3. Wait for response
4. Show results
5. Clean up

## Docker Services

The integration requires:

```bash
# Start Redpanda
cd ~/brain
docker-compose up -d redpanda

# Optional: Start Redis for caching
docker-compose up -d redis

# Check status
docker ps | grep -E "(redpanda|redis)"
```

## MCP Tools

Three MCP tools are available in `server.py`:

### `openrouter_event_request`

Send LLM request via event bus:

```
openrouter_event_request(
    query="Your question",
    task_type="simple",
    preferred_provider="groq",
    timeout_sec=30,
    wait_for_response=True
)
```

### `openrouter_event_subscribe`

Subscribe to responses for monitoring:

```
openrouter_event_subscribe(timeout_sec=60)
```

### `openrouter_event_status`

Check event bus system status:

```
openrouter_event_status()
```

## Use Cases

### 1. Background Analysis Agent

```python
# Agent continuously listens for new data
def analyze_background():
    for new_data in data_stream():
        request_id = publish_llm_request(
            f"Analyze this data: {new_data}",
            task_type="complex"
        )
        # Don't wait - just publish and continue
```

### 2. Multi-Agent Workflow

```python
# Agent 1: Research
research_id = publish_llm_request("Research topic X", task_type="complex")
research = wait_for_response(research_id)

# Agent 2: Summarize (uses Agent 1's output)
summary_id = publish_llm_request(f"Summarize: {research['response']}", task_type="simple")
summary = wait_for_response(summary_id)
```

### 3. Real-Time Assistance

```python
# User types question
user_question = input("Ask me anything: ")

# Send to event bus
request_id = publish_llm_request(user_question, task_type="general")

# Wait and show response
response = wait_for_response(request_id, timeout=30)
print(f"\n{response['response']}\n")
print(f"(via {response['provider_used']} in {response['latency_ms']}ms)")
```

## Troubleshooting

### Consumer Not Running

```bash
# Check if running
ps aux | grep event_bus_llm

# Start if not running
python3 -m mcp-servers.openrouter.event_bus_llm start &
```

### Kafka Connection Failed

```bash
# Check Redpanda is running
docker ps | grep redpanda

# Check logs
docker logs brain-redpanda

# Restart if needed
docker-compose restart redpanda
```

### Redis Connection Failed

Redis is optional. If not available, caching is disabled but everything else works.

```bash
# Check Redis
docker ps | grep redis

# Test connection
redis-cli -a BrainRedis2026 ping
```

### No Response Received

1. Check consumer is running
2. Check Kafka connectivity
3. Check provider availability: `openrouter_health()`
4. Increase timeout: `timeout_sec=60`

## Performance

Typical latencies:

| Scenario | Latency | Notes |
|----------|---------|-------|
| Cache hit | <10ms | Redis lookup |
| Groq (simple) | 100-200ms | Ultra-fast |
| Ollama (local) | 500-2000ms | Privacy-first |
| Claude | 2-5s | High quality |
| Event bus overhead | <5ms | Kafka is fast |

## Future Enhancements

- [ ] Priority queues for urgent requests
- [ ] Rate limiting per agent
- [ ] Cost tracking and limits
- [ ] A/B testing different providers
- [ ] Automatic prompt optimization
- [ ] Multi-LLM consensus for critical queries

## Files

| File | Purpose |
|------|---------|
| `event_bus_llm.py` | Event bus consumer and API |
| `server.py` | MCP tools for event bus |
| `EVENT_BUS_README.md` | This file |

## Related

- OpenRouter smart routing: `openrouter_smart_route()`
- Cascade fallback: `openrouter_cascade()`
- Provider health: `openrouter_health()`
- Redis reasoning: `redis_reasoning.py`

---

**Status**: ✅ Working (2026-04-02)  
**Tested**: Redpanda connection, message flow, caching, routing  
**Next**: Deploy background consumer as systemd service
