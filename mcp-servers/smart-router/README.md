# Smart Router MCP Server

Intelligent LLM routing for delegating tasks to multiple providers.

## Features

- **Multi-provider routing**: OpenAI, Gemini, Groq, Local Ollama
- **Task-based selection**: Routes code→OpenAI, fast→Groq, bulk→Local
- **Rate limiting**: Automatic tracking and fallback
- **Parallel queries**: Send to multiple providers simultaneously
- **Race mode**: Return fastest response

## Providers

| Provider | Model | Speed | Cost | Best For |
|----------|-------|-------|------|----------|
| OpenAI | gpt-4o | Medium | $0.005/1K | Code, Analysis |
| OpenAI Fast | gpt-4o-mini | Fast | $0.00015/1K | Quick tasks |
| Gemini | gemini-2.0-flash | Fast | FREE | Bulk, Analysis |
| Groq | llama-3.3-70b | Fastest | FREE | Chat, Speed |
| Local | llama3.1:8b | Medium | FREE | Private, Unlimited |

## Task Routes

- `code` → OpenAI → Gemini → Local
- `fast` → Groq → OpenAI-fast → Local
- `quality` → OpenAI → Gemini → Groq
- `bulk` → Local → Gemini → Groq
- `free` → Gemini → Groq → Local
- `private` → Local only

## MCP Tools

- `smart_delegate(prompt, task, prefer)` - Route to best provider
- `delegate_code(prompt)` - Code-optimized routing
- `delegate_fast(prompt)` - Speed-optimized routing
- `delegate_bulk(prompt)` - Unlimited routing
- `delegate_free(prompt)` - Free providers only
- `router_status()` - Check provider health
- `parallel_delegate(prompts, task)` - Process multiple in parallel
- `race_delegate(prompt)` - Return fastest response

## Setup

1. Set API keys in `~/brain/.env`:
```bash
OPENAI_API_KEY=sk-...
GEMINI_API_KEY=...
GROQ_API_KEY=gsk_...
```

2. Add to Claude config:
```json
{
  "mcpServers": {
    "smart-router": {
      "command": "python",
      "args": ["/Users/joe/brain/mcp-servers/smart-router/server.py"]
    }
  }
}
```

## Testing

```bash
# Unit tests
pytest tests/test_smart_router.py -v -k "not smoke"

# Smoke tests (requires API keys)
pytest tests/test_smart_router.py -v -m smoke
```

## CI/CD

Weekly smoke tests run every Sunday at 6 AM UTC via GitHub Actions.
