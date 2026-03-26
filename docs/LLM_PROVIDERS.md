# LLM Providers - Router & Smart Routing

> **Last verified:** 2026-03

This document is the **source of truth** for LLM routing support in agentic-brain.
It covers provider backends, routing behavior, model aliases, and known gaps.

---

## ✅ Supported Providers (Router)

| Provider | Module | Env Vars | Notes |
| --- | --- | --- | --- |
| **OpenAI** | `router/openai.py` | `OPENAI_API_KEY` | GPT-4o / GPT-4 / o1 family |
| **Azure OpenAI** | `router/azure_openai.py` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` | Deployment name used as `model` |
| **Anthropic (Claude)** | `router/anthropic.py` | `ANTHROPIC_API_KEY` | Claude 3/4 family |
| **Google Gemini** | `router/google.py` | `GOOGLE_API_KEY` | Gemini via AI Studio |
| **Groq** | `router/groq.py` | `GROQ_API_KEY` | Fast inference |
| **Ollama (Local)** | `router/ollama.py` | `OLLAMA_HOST` | Local-first, free |
| **OpenRouter** | `router/openrouter.py` | `OPENROUTER_API_KEY` (optional) | Aggregator with free models |
| **xAI / Grok** | `router/xai.py` | `XAI_API_KEY` | Grok models |
| **Together** | `router/together.py` | `TOGETHER_API_KEY` | Free credits |

---

## 🧭 Routing Behavior

### LLMRouter (default)
- **Primary path:** `router/routing.py`
- **Fallback chain:**
  - `OLLAMA (llama3.1:8b)` → `OLLAMA (llama3.2:3b)` → `OPENROUTER (free model)`
- **Rate limit handling:**
  - Provider backends raise `RateLimitError` on `429`; LLMRouter retries fallback chain.
- **Cost optimization:**
  - Semantic prompt cache (`cache/semantic_cache.py`) reduces repeat calls.

### SmartRouter (task-based)
- **Primary path:** `smart_router/core.py` (+ `smart_router/workers.py`)
- **Task-based routing:**
  - `code` → OpenAI → Azure OpenAI → Groq → Local
  - `fast` → Groq → Gemini → Local
  - `bulk` → Local → Together → Groq
- **Modes:**
  - `DEDICATED` (task routes), `CASCADE` (free-first), `PARALLEL` (all workers), `CONSENSUS` (multi-worker)
- **Cost optimization:**
  - `CASCADE` mode + `SecurityPosture(prefer_free_workers=True)`

---

## 🧩 Model Aliases

Defined in `model_aliases.py` for quick switching.

- **Local:** `L1`, `L2`, `L3`, `L4`
- **Claude:** `CL`, `CL2`, `CL3`
- **OpenAI:** `OP`, `OP2`, `OP3`
- **Azure OpenAI:** `AZ`, `AZ2`
- **Gemini:** `GO`, `GO2`
- **Groq:** `GR`, `GR2`
- **OpenRouter:** `OR`, `OR2`
- **xAI Grok:** `XK`, `XK2`

---

## ⚠️ Known Gaps / TODO

1. **SmartRouter not wired as default**
   - Agent + Chatbot currently use `LLMRouter` by default.
   - SmartRouter is opt-in (import from `agentic_brain.smart_router`).

2. **RateLimiter not yet enforced in router path**
   - `rate_limiter.py` exists but is not wired into LLMRouter/SmartRouter.
   - Current handling relies on provider `429` errors and fallback routing.

---

## ✅ Verification Checklist

- [x] OpenAI provider implemented
- [x] Anthropic provider implemented
- [x] Google Gemini provider implemented
- [x] Groq provider implemented
- [x] Ollama provider implemented
- [x] OpenRouter provider implemented
- [x] xAI/Grok provider implemented
- [x] Azure OpenAI provider implemented
- [x] Task-based routing present (SmartRouter)
- [x] Fallback chain present (LLMRouter)
- [x] Cost optimization present (cache + cascade)
- [x] Rate limit handling present (fallback on 429)
