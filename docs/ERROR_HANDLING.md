# Error Handling

Core error types live in `agentic_brain.core.exceptions`:

- `AgenticBrainError`
- `GraphConnectionError`
- `EmbeddingError`
- `LLMError`
- `RateLimitError`
- `ValidationError`

Retry helpers live in `agentic_brain.core.retry`:

- `retry_with_backoff`
- `circuit_breaker`
- `timeout`

## Usage

```python
from agentic_brain.core.exceptions import LLMError, RateLimitError
from agentic_brain.core.retry import retry_with_backoff, timeout

@retry_with_backoff(attempts=4, initial_delay=0.25)
@timeout(30)
def call_llm() -> str:
    ...

try:
    call_llm()
except RateLimitError as exc:
    # Wait exc.context["retry_after"] seconds
    raise
except LLMError as exc:
    # Provider/model failure
    raise
```

## Guidance

- Use `ValidationError` for bad input and configuration.
- Use `RateLimitError` for 429/throttling responses.
- Use `GraphConnectionError` for Neo4j/graph connectivity issues.
- Use `EmbeddingError` for embedding provider failures.
- Use `LLMError` for provider/model failures.
- Keep retries for transient failures only.
- Never retry `ValidationError`.

