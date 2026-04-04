# 🚀 Event Bus LLM - Quick Reference

## 🎯 Quick Start (30 seconds)

```bash
# 1. Start Redpanda (if not running)
cd ~/brain && docker-compose up -d redpanda

# 2. Start consumer (background)
cd ~/brain/mcp-servers/openrouter
python3 event_bus_llm.py start &

# 3. Test it
python3 -c "
from event_bus_llm import publish_llm_request, wait_for_response
r = publish_llm_request('What is 2+2?', 'simple')
print(wait_for_response(r, 30)['response'])
"
```

## 📡 Topics

| Topic | Use |
|-------|-----|
| `brain.llm.request` | → Send requests |
| `brain.llm.response` | ← Get responses |
| `brain.llm.status` | Monitor health |

## 🔧 MCP Tools

```bash
# Send request via CLI
openrouter_event_request "Your question" simple

# Monitor responses
openrouter_event_subscribe 60

# Check health
openrouter_event_status
```

## 🐍 Python API

```python
from event_bus_llm import *

# Send + wait (sync)
req_id = publish_llm_request("Question?", "simple")
resp = wait_for_response(req_id, 30)
print(resp["response"])

# Send only (async)
req_id = publish_llm_request("Question?", "simple")
# Response arrives on brain.llm.response topic

# Subscribe to all
def handler(r): print(r["response"])
subscribe_responses(handler)
```

## 📊 Task Types

| Type | Routes To | Speed |
|------|-----------|-------|
| `simple` | Groq | 100ms |
| `complex` | Claude | 2s |
| `coding` | Groq 70B | 200ms |
| `general` | Auto | Varies |

## 🔍 Troubleshooting

```bash
# Check consumer
ps aux | grep event_bus_llm

# Check Kafka
docker ps | grep redpanda

# Check Redis (optional)
redis-cli ping

# Restart everything
docker-compose restart redpanda redis
python3 event_bus_llm.py start &
```

## 📖 Full Docs

- `EVENT_BUS_README.md` - Complete guide
- `INTEGRATION_SUMMARY.md` - What was built
- `event_bus_llm.py` - Source code

## ✨ Key Features

- ✅ Smart routing (Groq → Ollama → Cloud)
- ✅ Redis caching (1 hour TTL)
- ✅ Multi-agent support
- ✅ Async/sync modes
- ✅ Graceful fallback
- ✅ MCP integration

---

**Status**: ✅ Working | **Date**: 2026-04-02
