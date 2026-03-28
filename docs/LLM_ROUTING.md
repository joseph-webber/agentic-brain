# LLM Routing

This document explains the Agentic Brain LLM routing stack: the lightweight `LLMRouterCore`, the application-facing `LLMRouter`, and the parallel worker-based `SmartRouter`.

## Overview

The routing system exists so the project can:

- use local models first when privacy, cost, or offline operation matter
- fall back automatically when a provider is unavailable, rate limited, or slow
- route different task types to better-suited models
- support a single calling style across multiple providers
- track token usage and estimated cost
- add higher-level orchestration without changing every caller

At a high level:

- **`LLMRouterCore`** is the smallest reusable routing layer
- **`LLMRouter`** is the main production router used by most application code
- **`SmartRouter`** is a separate master/worker orchestration layer for multi-worker dispatch

---

## Architecture Diagram

```text
                               ┌─────────────────────────────┐
                               │        Application          │
                               │ agents, APIs, services, CLI │
                               └──────────────┬──────────────┘
                                              │
                     ┌────────────────────────┼────────────────────────┐
                     │                        │                        │
                     ▼                        ▼                        ▼
         ┌────────────────────┐   ┌────────────────────┐   ┌────────────────────┐
         │   LLMRouterCore    │   │     LLMRouter      │   │    SmartRouter     │
         │ lightweight core   │   │ full-featured      │   │ master/worker      │
         │ alias + retry      │   │ app-facing router  │   │ parallel routing   │
         └─────────┬──────────┘   └─────────┬──────────┘   └─────────┬──────────┘
                   │                        │                        │
                   │ inherits into          │ uses provider modules  │ uses worker adapters
                   └──────────────┬─────────┘                        │
                                  │                                  │
                                  ▼                                  ▼
                       ┌────────────────────┐             ┌──────────────────────┐
                       │ shared concepts    │             │ worker pool          │
                       │ messages, aliases, │             │ openai, azure, groq,│
                       │ retry/backoff      │             │ gemini, local,       │
                       └────────────────────┘             │ together, deepseek,  │
                                                          │ openrouter           │
                                                          └──────────────────────┘

Provider hierarchy
------------------

LLMRouterCore
  ├─ Ollama
  ├─ OpenAI
  ├─ Anthropic
  └─ OpenRouter

LLMRouter
  ├─ Ollama
  ├─ OpenAI
  ├─ Azure OpenAI
  ├─ Anthropic
  ├─ OpenRouter
  ├─ Groq
  ├─ Together
  ├─ Google
  └─ xAI

SmartRouter workers
  ├─ openai
  ├─ azure_openai
  ├─ groq
  ├─ gemini
  ├─ local
  ├─ together
  ├─ deepseek
  └─ openrouter
```

---

## Quick Start

### Which router should I use?

| Router | Use it when | Best for |
|---|---|---|
| `LLMRouterCore` | You want a minimal dependency-light router | library code, simple services, tests, basic fallback |
| `LLMRouter` | You want the main project router | most application features, caching, provider expansion, streaming |
| `SmartRouter` | You want worker orchestration rather than single-route chat | parallel execution, free-first routing, task-specific worker dispatch |

### Basic usage

#### `LLMRouterCore`

```python
from agentic_brain.llm.router import LLMRouterCore

router = LLMRouterCore()
response = await router.chat(message="Explain event sourcing", model="CL2")
print(response.content)
```

#### `LLMRouter`

```python
from agentic_brain.router.routing import LLMRouter

router = LLMRouter()
response = await router.chat("Write a Python function to debounce calls")
print(response.provider, response.model)
print(response.content)
```

#### `SmartRouter`

```python
from agentic_brain.smart_router.core import SmartRouter, SmashMode

router = SmartRouter()
result = await router.route(
    task_type="code",
    prompt="Review this Python function for bugs",
    mode=SmashMode.DEDICATED,
)
print(result.provider)
print(result.response)
```

### Sync wrappers

`LLMRouterCore` and `LLMRouter` both expose sync wrappers:

```python
response = LLMRouter().chat_sync("Hello")
```

---

## Routers Explained

### 1. `LLMRouterCore`

**Source:** `src/agentic_brain/llm/router.py`

`LLMRouterCore` is the smallest common routing layer. It standardizes message format, resolves aliases, retries transient failures, and walks an ordered route list until one succeeds.

### What it does

- normalizes `message`, `system`, or full `messages` into one internal format
- resolves friendly aliases like `local`, `claude`, `gpt-fast`, `L1`, `CL`, `OP2`
- estimates token usage and approximate cost
- retries retryable HTTP failures and rate limits with backoff
- tries an ordered sequence of model routes for fallback

### Supported providers

`LLMRouterCore` supports these providers directly:

- `ollama`
- `openai`
- `anthropic`
- `openrouter`

### Important notes

- It is intentionally lightweight.
- Provider dispatch is narrower than the full router.
- Alias auto-loading is primarily geared around Anthropic, OpenAI, and Ollama aliases plus friendly aliases such as `local`, `gpt`, and `claude`.
- You can still pass explicit provider/model combinations directly.

### Typical use cases

- small async services
- tests that need a real router abstraction without full stack behavior
- direct multi-model fallback using `models=[...]`

### Example

```python
from agentic_brain.llm.router import LLMRouterCore
from agentic_brain.router.config import Provider

router = LLMRouterCore()
response = await router.chat(
    message="Summarize this architecture",
    provider=Provider.OPENAI,
    model="gpt-4o-mini",
)
```

### Explicit fallback list

```python
response = await router.chat(
    message="Give me a short summary",
    models=["L1", "OP2", "CL2"],
)
```

The router will try those routes in order, applying retry/backoff per route before moving on.

---

### 2. `LLMRouter`

**Source:** `src/agentic_brain/router/routing.py`

`LLMRouter` extends `LLMRouterCore` and is the main production router for the project.

### What it adds on top of the core

- more provider backends
- smart task routing when provider/model are not explicitly set
- semantic prompt cache
- optional Redis inter-bot cache
- HTTP connection pooling
- async and sync interfaces
- streaming support
- provider availability checks
- optional integration with `UnifiedBrain` routing

### Built-in routing heuristics

If you do not force a provider or model, `LLMRouter.chat()` calls `smart_route()`:

- **short/simple prompts** prefer the fastest configured route
- **analysis/reasoning prompts** prefer the reasoning chain
- **code prompts** prefer the code chain
- otherwise it uses the configured default provider/model or general fallback chain

### Default chain definitions

`LLMRouter` includes several route lists:

- `FALLBACK_CHAIN`
- `FASTEST_CHAIN`
- `CODE_CHAIN`
- `REASONING_CHAIN`

These are provider/model pairs, not alias codes.

### Supported providers

- `ollama`
- `openai`
- `azure_openai`
- `anthropic`
- `openrouter`
- `groq`
- `together`
- `google`
- `xai`

### Cache behavior

When `use_cache=True`:

1. semantic cache is checked first
2. Redis inter-bot cache is checked second if configured
3. provider request is executed
4. successful response is cached

### Streaming behavior

`LLMRouter.stream()` supports streaming across all major providers wired in the router.

### Example

```python
from agentic_brain.router.routing import LLMRouter

router = LLMRouter()
response = await router.chat(
    "Refactor this SQL query for readability",
    persona="default",
)
print(response.content)
print(response.cached)
```

---

### 3. `SmartRouter`

**Source:** `src/agentic_brain/smart_router/core.py`

`SmartRouter` is a different abstraction from `LLMRouter`. Instead of selecting one provider/model path for a chat call, it coordinates **workers**.

### What it does

- maps task types to preferred workers
- supports multiple execution modes
- can run free-first or dedicated routes
- tracks worker heat for lightweight load balancing
- records per-worker stats
- optionally filters workers through a security posture

### Task routes

Built-in task types are:

- `code`
- `fast`
- `free`
- `bulk`
- `complex`
- `creative`

Each task type maps to an ordered worker list.

### Execution modes

| Mode | Meaning |
|---|---|
| `TURBO` | fire all selected workers and use the fastest winning result |
| `CONSENSUS` | run a subset of cool workers and compare/coordinate results |
| `CASCADE` | try free workers first, then fall back |
| `DEDICATED` | use the ordered task-specific worker list with fallback |

### Posture-aware routing

`SmartRouter.route()` accepts an optional `posture` object. When present it can:

- filter out disallowed workers
- reorder workers to prefer free ones
- constrain execution based on policy/security context

### Worker model source of truth

Default worker configs are created in `_setup_default_workers()` and include metadata such as:

- model name
- API key environment variable
- endpoint
- rate limit
- cost per 1K tokens
- free/local flags
- typical latency

### Example

```python
from agentic_brain.smart_router.core import SmartRouter, SmashMode

router = SmartRouter()
result = await router.route(
    task_type="fast",
    prompt="Give me three title options",
    mode=SmashMode.TURBO,
    timeout=10.0,
)
print(result.provider, result.elapsed)
print(result.response)
```

---

## Providers

### Provider matrix

| Provider | Core | Full router | SmartRouter worker |
|---|---:|---:|---:|
| Ollama | yes | yes | yes (`local`) |
| OpenAI | yes | yes | yes |
| Azure OpenAI | no | yes | yes |
| Anthropic | yes | yes | no direct worker in `SmartRouter` defaults |
| OpenRouter | yes | yes | yes |
| Groq | no | yes | yes |
| Together | no | yes | yes |
| Google Gemini | no | yes | yes (`gemini`) |
| xAI | no | yes | no default worker |
| DeepSeek | no | no direct `LLMRouter` backend | yes |

### Configuration

### Environment variables

| Provider | Required environment variables |
|---|---|
| Ollama | `OLLAMA_HOST` (optional, defaults to `http://localhost:11434`) |
| OpenAI | `OPENAI_API_KEY` |
| Azure OpenAI | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT` |
| Anthropic | `ANTHROPIC_API_KEY` |
| OpenRouter | `OPENROUTER_API_KEY` optional for some free-model flows |
| Groq | `GROQ_API_KEY` |
| Together | `TOGETHER_API_KEY` |
| Google Gemini | `GOOGLE_API_KEY` |
| xAI | `XAI_API_KEY` |
| DeepSeek worker | `DEEPSEEK_API_KEY` |

### Additional Azure setting

Azure OpenAI also supports:

- `AZURE_OPENAI_API_VERSION`

### Config object example

```python
from agentic_brain.router.config import RouterConfig, Provider
from agentic_brain.router.routing import LLMRouter

config = RouterConfig(
    default_provider=Provider.OLLAMA,
    default_model="llama3.1:8b",
    priority_models=["L2", "OP2", "CL2"],
    use_http_pool=True,
    cache_enabled=True,
)

router = LLMRouter(config=config)
```

### Direct config fields

The main `RouterConfig` fields relevant to routing are:

- `default_provider`
- `default_model`
- `priority_models`
- `model_aliases`
- `fallback_enabled`
- `max_retries`
- `backoff_base_seconds`
- `backoff_max_seconds`
- `use_http_pool`
- `cache_enabled`
- cache backend settings
- provider-specific credentials and timeouts

---

## Model Aliases

**Source:** `src/agentic_brain/model_aliases.py`

The alias system provides short human-friendly model codes.

### Naming scheme

```text
[PROVIDER][TIER]

Provider:
  L  = local Ollama
  CL = Claude / Anthropic
  OP = OpenAI
  AZ = Azure OpenAI
  GO = Google Gemini
  GR = Groq
  OR = OpenRouter
  XK = xAI / Grok

Tier:
  blank or 1 = best/default
  2          = cheaper/faster
  3          = premium/special
  4          = embeddings/special
```

### Common aliases

| Alias | Provider | Model | Meaning |
|---|---|---|---|
| `L1` | Ollama | `llama3.2:3b` | local fast |
| `L2` | Ollama | `llama3.1:8b` | local quality |
| `L3` | Ollama | `mistral:7b` | local alternative |
| `L4` | Ollama | `nomic-embed-text` | embeddings only |
| `CL` / `CL1` | Anthropic | `claude-sonnet-4-20250514` | Claude best |
| `CL2` | Anthropic | `claude-3-haiku-20240307` | Claude cheap/fast |
| `CL3` | Anthropic | `claude-opus-4-20250514` | Claude premium |
| `OP` / `OP1` | OpenAI | `gpt-4o` | OpenAI best |
| `OP2` | OpenAI | `gpt-4o-mini` | OpenAI cheap/fast |
| `OP3` | OpenAI | `o1` | OpenAI reasoning |
| `AZ` | Azure OpenAI | `gpt-4o` | Azure best |
| `AZ2` | Azure OpenAI | `gpt-4o-mini` | Azure cheaper |
| `GO` / `GO1` | Google | `gemini-2.5-flash` | Gemini fast |
| `GO2` | Google | `gemini-2.5-pro` | Gemini quality |
| `GR` / `GR1` | Groq | `llama-3.3-70b-versatile` | Groq fast |
| `GR2` | Groq | `mixtral-8x7b-32768` | Groq alternate |
| `OR` | OpenRouter | `meta-llama/llama-3.1-8b-instruct:free` | OpenRouter free |
| `OR2` | OpenRouter | `openai/gpt-4o-mini` | OpenRouter cheap |
| `XK` / `XK1` | xAI | `grok-4.1-fast` | Grok fast |
| `XK2` | xAI | `grok-3-mini` | Grok budget |

### Friendly aliases in `LLMRouterCore`

`LLMRouterCore` also defines readable names such as:

- `local`
- `local-fast`
- `ollama`
- `gpt`
- `gpt-fast`
- `claude`
- `claude-fast`
- `sonnet`
- `haiku`

### Adding custom aliases at runtime

Use `RouterConfig.model_aliases` or the `aliases=` constructor argument.

```python
from agentic_brain.llm.router import LLMRouterCore
from agentic_brain.router.config import RouterConfig

config = RouterConfig(model_aliases={
    "cheap-code": "OP2",
    "safe-fast": "CL2",
})

router = LLMRouterCore(config=config)
response = await router.chat(message="Explain this function", model="cheap-code")
```

### Adding permanent built-in aliases

If you want a new globally-defined alias code such as `MY1`, add it to `MODEL_ALIASES` in:

- `src/agentic_brain/model_aliases.py`

Each entry should include at least:

- `provider`
- `model`
- `description`
- `tier`
- optionally `fallback`

---

## Fallback Chains

Fallback exists at more than one layer in this codebase.

### 1. `LLMRouterCore` fallback

`LLMRouterCore` builds an ordered list of `ModelRoute` values from:

- the explicit `models=[...]` argument, or
- the resolved primary model, followed by
- `config.priority_models`

For each route it:

1. dispatches the request
2. retries transient failures with exponential backoff
3. respects `Retry-After` when available
4. moves to the next route if the current one still fails

### Example

```python
response = await router.chat(
    message="Summarize this",
    models=["L1", "OP2", "CL2"],
)
```

### 2. `LLMRouter` fallback

`LLMRouter` chooses a primary route, then builds fallback routes with `_fallback_routes_for()`.

Behavior:

- if the request looks like code, it biases toward `CODE_CHAIN`
- if the request looks like reasoning/analysis, it biases toward `REASONING_CHAIN`
- otherwise it falls back through the general `FALLBACK_CHAIN`
- duplicates are removed while preserving order

### Built-in route chains in `LLMRouter`

#### General fallback

```text
Ollama llama3.1:8b
→ Groq llama-3.1-8b-instant
→ OpenRouter meta-llama/llama-3-8b-instruct:free
→ OpenAI gpt-4o-mini
→ Anthropic claude-3-haiku-20240307
→ Together meta-llama/Llama-3.1-8B-Instruct-Turbo
```

#### Fastest chain

```text
Ollama llama3.2:3b
→ Groq llama-3.1-8b-instant
→ OpenRouter free Llama
→ OpenAI gpt-4o-mini
→ Anthropic Haiku
→ Together Llama
→ Google gemini-1.5-flash
→ xAI grok-2-mini
```

#### Code chain

```text
Anthropic claude-3-5-sonnet-20241022
→ OpenAI gpt-4o
→ Ollama llama3.1:8b
```

#### Reasoning chain

```text
Anthropic claude-3-sonnet-20240229
→ OpenAI gpt-4o
→ Ollama llama3.1:8b
```

### 3. Alias-level fallback definitions

`model_aliases.py` also defines alias-oriented fallback chains:

- `FALLBACK_CHAIN`
- `FALLBACK_CHAIN_SPEED`
- `FALLBACK_CHAIN_QUALITY`
- `FALLBACK_CHAIN_FREE`
- `FALLBACK_CHAIN_CODING`
- `FALLBACK_CHAIN_PRESERVE_CREDITS`

These are useful when you want policy or UX-level routing using alias codes rather than provider/model tuples.

### Speed vs quality vs cost

| Goal | Alias chain |
|---|---|
| Speed | `GR -> L1 -> GO -> XK -> OP2 -> CL2 -> L2` |
| Quality | `CL -> OP -> L2 -> CL2 -> OP2 -> L1` |
| Free only | `L1 -> L2 -> GO -> GR -> XK` |
| Coding | `OP -> CL -> L2 -> OP2 -> CL2 -> L1` |
| Preserve credits | `L1 -> L2 -> GO -> GR -> XK` |

### 4. `SmartRouter` fallback

`SmartRouter` fallback depends on execution mode:

- `DEDICATED`: ordered worker fallback
- `CASCADE`: free-first worker cascade
- `TURBO`: multiple workers raced in parallel
- `CONSENSUS`: selected cool workers coordinated together

---

## Examples

### 1. Simple chat

```python
from agentic_brain.router.routing import LLMRouter

router = LLMRouter()
response = await router.chat("What is CQRS?")
print(response.content)
```

### 2. Force a provider/model

```python
from agentic_brain.router.config import Provider
from agentic_brain.router.routing import LLMRouter

router = LLMRouter()
response = await router.chat(
    "Explain this API design",
    provider=Provider.ANTHROPIC,
    model="claude-3-5-sonnet-20241022",
)
```

### 3. Use alias-based routing with the core router

```python
from agentic_brain.llm.router import LLMRouterCore

router = LLMRouterCore()
response = await router.chat(message="Write a commit message", model="OP2")
print(response.model)
```

### 4. Streaming

```python
from agentic_brain.router.routing import LLMRouter
from agentic_brain.router.config import Provider

router = LLMRouter()
async for token in router.stream(
    "Write a haiku about distributed systems",
    provider=Provider.OPENAI,
    model="gpt-4o-mini",
):
    print(token, end="", flush=True)
```

### 5. Multi-provider fallback

### Core router with explicit ordered models

```python
from agentic_brain.llm.router import LLMRouterCore

router = LLMRouterCore()
response = await router.chat(
    message="Summarize this design doc",
    models=["L2", "OP2", "CL2"],
)
print(response.provider, response.model)
```

### Full router with automatic fallback

```python
from agentic_brain.router.routing import LLMRouter

router = LLMRouter()
response = await router.chat("Analyze this architecture for bottlenecks")
print(response.provider, response.model)
```

### 6. Smart routing with workers

```python
from agentic_brain.smart_router.core import SmartRouter, SmashMode

router = SmartRouter()
result = await router.route(
    task_type="free",
    prompt="Generate ten product taglines",
    mode=SmashMode.CASCADE,
)
print(result.mode)
print(result.provider)
print(result.response)
```

### 7. Distribute a batch across providers

```python
from agentic_brain.router.routing import LLMRouter

router = LLMRouter()
tasks = [
    "Summarize document A",
    "Summarize document B",
    "Write unit tests for parser",
]

plan = router.distribute_load(tasks)
for route, assigned in plan.items():
    print(route, assigned)
```

---

## Practical Guidance

- Use **`LLMRouter` by default** for app code.
- Use **`LLMRouterCore`** when you want a smaller abstraction or direct ordered routing.
- Use **`SmartRouter`** when the problem is orchestration, not just provider selection.
- Use **aliases** for human-facing configuration.
- Use **explicit provider/model tuples** when reproducibility matters.
- Keep **local models first** when privacy and cost matter.

---

## Source Files

- `src/agentic_brain/llm/router.py`
- `src/agentic_brain/router/routing.py`
- `src/agentic_brain/smart_router/core.py`
- `src/agentic_brain/model_aliases.py`
- `src/agentic_brain/router/config.py`
