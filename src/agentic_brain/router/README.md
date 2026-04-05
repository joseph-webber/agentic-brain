# Router Package

The `agentic_brain.router` package provides the production LLM routing layer. It selects a provider and model, applies routing heuristics, checks provider availability, and falls back across multiple backends when required.

## Router architecture overview

```
agentic_brain.router
├── __init__.py          # Public exports and compatibility shims
├── config.py            # Provider, model, message, and router config types
├── routing.py           # Primary production router (LLMRouter)
├── smart_router.py      # Bridge to the advanced smart router package
├── provider_checker.py  # Availability and setup diagnostics
├── http.py              # Shared HTTP transport helpers
└── provider modules     # OpenAI, Anthropic, Groq, Google, xAI, Together, OpenRouter, Ollama, Azure OpenAI
```

### Execution flow
1. Normalize the message payload.
2. Select a route with `smart_route()`.
3. Check semantic cache and Redis cache.
4. Call the selected provider.
5. Retry through the fallback chain on failure or `RateLimitError`.
6. Store successful responses in cache.

`LLMRouter` is the primary public entry point. `SmartRouter` remains available for advanced orchestration and security posture workflows.

## Supported LLM providers

| Provider | Module | Config source |
| --- | --- | --- |
| Ollama | `router/ollama.py` | `OLLAMA_HOST` |
| OpenRouter | `router/openrouter.py` | `OPENROUTER_API_KEY` |
| OpenAI | `router/openai.py` | `OPENAI_API_KEY` |
| Azure OpenAI | `router/azure_openai.py` | `AZURE_OPENAI_API_KEY`, `AZURE_OPENAI_ENDPOINT`, `AZURE_OPENAI_DEPLOYMENT`, `AZURE_OPENAI_API_VERSION` |
| Anthropic | `router/anthropic.py` | `ANTHROPIC_API_KEY` |
| Groq | `router/groq.py` | `GROQ_API_KEY` |
| Together | `router/together.py` | `TOGETHER_API_KEY` |
| Google | `router/google.py` | `GOOGLE_API_KEY` |
| xAI | `router/xai.py` | `XAI_API_KEY` |

## Routing strategies

### Cost
- Prefer local models first when available.
- Use OpenRouter free models when a cloud fallback is needed.
- Cache repeated prompts with semantic caching and Redis coordination.
- Track usage with `RouterConfig.cost_tracking_enabled`.

### Latency
- Short, simple prompts route to the fastest available chain.
- HTTP pooling reduces request overhead.
- Provider selection uses availability checks and least-used route balancing.
- Fast models are preferred for brief non-technical prompts.

### Capability
- Code-oriented prompts prefer the code chain.
- Analysis and reasoning prompts prefer the reasoning chain.
- Default routing falls back to the configured provider or the main fallback chain.
- Provider selection respects security posture and provider permissions when enabled.

## Fallback chains

### Default fallback chain
1. `OLLAMA / llama3.1:8b`
2. `GROQ / llama-3.1-8b-instant`
3. `OPENROUTER / meta-llama/llama-3-8b-instruct:free`
4. `OPENAI / gpt-4o-mini`
5. `ANTHROPIC / claude-3-haiku-20240307`
6. `TOGETHER / meta-llama/Llama-3.1-8B-Instruct-Turbo`

### Fastest chain
1. `OLLAMA / llama3.2:3b`
2. `GROQ / llama-3.1-8b-instant`
3. `OPENROUTER / meta-llama/llama-3-8b-instruct:free`
4. `OPENAI / gpt-4o-mini`
5. `ANTHROPIC / claude-3-haiku-20240307`
6. `TOGETHER / meta-llama/Llama-3.1-8B-Instruct-Turbo`
7. `GOOGLE / gemini-1.5-flash`
8. `XAI / grok-2-mini`

### Code chain
1. `ANTHROPIC / claude-3-5-sonnet-20241022`
2. `OPENAI / gpt-4o`
3. `OLLAMA / llama3.1:8b`

### Reasoning chain
1. `ANTHROPIC / claude-3-sonnet-20240229`
2. `OPENAI / gpt-4o`
3. `OLLAMA / llama3.1:8b`

Fallback execution is triggered by provider failure, a rate limit response, or explicit route exhaustion when the primary provider is unavailable.

## Configuration guide

### Environment variables

| Variable | Purpose |
| --- | --- |
| `OLLAMA_HOST` | Local Ollama endpoint |
| `OPENAI_API_KEY` | OpenAI authentication |
| `AZURE_OPENAI_API_KEY` | Azure OpenAI authentication |
| `AZURE_OPENAI_ENDPOINT` | Azure OpenAI endpoint |
| `AZURE_OPENAI_DEPLOYMENT` | Azure deployment name |
| `AZURE_OPENAI_API_VERSION` | Azure API version |
| `ANTHROPIC_API_KEY` | Anthropic authentication |
| `OPENROUTER_API_KEY` | OpenRouter authentication |
| `GROQ_API_KEY` | Groq authentication |
| `TOGETHER_API_KEY` | Together authentication |
| `GOOGLE_API_KEY` | Google Gemini authentication |
| `XAI_API_KEY` | xAI authentication |

### RouterConfig settings

| Setting | Default | Effect |
| --- | --- | --- |
| `default_provider` | `Provider.OLLAMA` | Primary provider when routing is not explicit |
| `default_model` | `llama3.1:8b` | Default model name |
| `fallback_enabled` | `True` | Enables fallback chains |
| `use_http_pool` | `True` | Enables pooled HTTP transport |
| `cache_enabled` | `True` | Enables semantic caching |
| `cache_ttl_seconds` | `3600` | Cache entry lifetime |
| `cache_backend` | `memory` | Cache backend selection |
| `timeout` | `60` | Default request timeout |
| `max_retries` | `3` | Retry attempts per provider |
| `cost_tracking_enabled` | `True` | Tracks token and cost usage |

### Minimal configuration example

```python
from agentic_brain.router import LLMRouter, Provider, RouterConfig

config = RouterConfig(
    default_provider=Provider.OLLAMA,
    fallback_enabled=True,
    cache_enabled=True,
)

router = LLMRouter(config=config)
```

## Provider comparison table

| Provider | Primary strength | Latency profile | Cost profile | Typical use |
| --- | --- | --- | --- | --- |
| Ollama | Local control | Low once warmed | Lowest | Private and offline workloads |
| OpenRouter | Aggregated access | Variable | Low to medium | Free or mixed-provider routing |
| OpenAI | Broad capability | Low to medium | Medium to high | General-purpose production tasks |
| Azure OpenAI | Enterprise controls | Medium | Medium to high | Managed enterprise deployments |
| Anthropic | Long-context reasoning | Medium | Medium to high | Analysis, reasoning, code |
| Groq | Fast inference | Very low | Low to medium | Latency-sensitive prompts |
| Together | Model diversity | Low to medium | Low to medium | Alternate cloud fallback |
| Google | Fast lightweight models | Very low to low | Low | Simple and high-throughput tasks |
| xAI | Alternative cloud option | Low to medium | Low to medium | Secondary cloud fallback |

## Usage notes

- Import `LLMRouter` from `agentic_brain.router` for standard production use.
- Use `ProviderChecker` to validate runtime availability before deployment.
- Use `SmartRouter` only when advanced posture and orchestration behavior is required.
