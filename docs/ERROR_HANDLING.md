# Error Handling Guide

Agentic Brain uses a structured exception hierarchy to provide actionable error messages with debugging context. Every error includes:

- **Message**: User-friendly description
- **Cause**: Root cause analysis  
- **Fix**: Suggested remediation steps
- **Debug Info**: Additional context for troubleshooting

## Exception Hierarchy

```
AgenticBrainError (base)
├── Neo4jConnectionError    # Database connection issues
├── LLMProviderError        # LLM provider failures
├── LLMResponseError        # Response parsing failures
├── MemoryError             # Memory operation failures
├── TransportError          # Transport layer errors
├── ConfigurationError      # Invalid/missing config
├── RateLimitError          # Rate limit exceeded
├── SessionError            # Session management errors
├── ValidationError         # Input validation failures
├── TimeoutError            # Operation timeouts
├── APIError                # API request failures
├── ModelNotFoundError      # Model not available
└── AuthenticationError     # Authentication failures
```

## Usage Examples

### Raising Exceptions

```python
from agentic_brain.exceptions import (
    LLMProviderError,
    ConfigurationError,
    ValidationError,
)

# LLM provider failure
raise LLMProviderError(
    provider="openai",
    model="gpt-4o",
    original_error=e
)

# Missing configuration
raise ConfigurationError(
    config_key="OPENAI_API_KEY",
    expected="valid API key",
    example="sk-..."
)

# Validation error
raise ValidationError(
    field="temperature",
    expected="float between 0.0 and 2.0",
    got=str(value)
)
```

### Catching Exceptions

```python
from agentic_brain.exceptions import AgenticBrainError, LLMProviderError

try:
    response = await router.chat(messages)
except LLMProviderError as e:
    # Handle specific LLM failures
    logger.error(f"LLM failed: {e.message}")
    logger.debug(f"Debug info: {e.debug_info}")
    # Try fallback provider
except AgenticBrainError as e:
    # Handle any agentic-brain error
    logger.error(str(e))  # Full formatted message
```

## Exception Reference

### Neo4jConnectionError

**When**: Cannot connect to Neo4j database

```python
from agentic_brain.exceptions import Neo4jConnectionError

raise Neo4jConnectionError(
    uri="bolt://localhost:7687",
    original_error=connection_error
)
```

**Output**:
```
❌ Failed to connect to Neo4j database
  └─ Cause: Connection refused
  └─ Fix: ✓ Check Neo4j is running at bolt://localhost:7687
          ✓ Try: docker run -d -p 7687:7687 -e NEO4J_AUTH=neo4j/password neo4j:latest
          ✓ Verify credentials and URI format
```

### LLMProviderError

**When**: LLM provider cannot process request

```python
from agentic_brain.exceptions import LLMProviderError

raise LLMProviderError(
    provider="ollama",
    model="llama3.2",
    original_error=timeout_error
)
```

**Provider-specific fixes included for**: Ollama, OpenAI, Anthropic, OpenRouter

### RateLimitError

**When**: API rate limits exceeded

```python
from agentic_brain.exceptions import RateLimitError

raise RateLimitError(
    limit=100,
    window="minute",
    retry_after=60
)
```

### ConfigurationError

**When**: Required configuration is missing or invalid

```python
from agentic_brain.exceptions import ConfigurationError

raise ConfigurationError(
    config_key="JWT_SECRET",
    expected="32+ character secret",
    example="your-super-secret-key-here"
)
```

### TransportError

**When**: Transport layer operations fail

```python
from agentic_brain.exceptions import TransportError

raise TransportError(
    transport="websocket",
    operation="connect",
    original_error=network_error
)
```

### TimeoutError

**When**: Operations exceed time limits

```python
from agentic_brain.exceptions import TimeoutError

raise TimeoutError(
    operation="LLM chat completion",
    timeout_seconds=30,
    original_error=asyncio_timeout
)
```

### ValidationError

**When**: Input validation fails

```python
from agentic_brain.exceptions import ValidationError

raise ValidationError(
    field="model",
    expected="string model name",
    got="None"
)
```

### AuthenticationError

**When**: Authentication operations fail

```python
from agentic_brain.exceptions import AuthenticationError

raise AuthenticationError(
    message="Token expired",
    cause="Token was issued more than 24 hours ago",
    token_type="access"
)
```

## Best Practices

### 1. Always Wrap Original Exceptions

```python
try:
    result = external_api.call()
except ExternalAPIError as e:
    raise LLMProviderError(
        provider="external",
        model="model-name",
        original_error=e  # Preserve original for debugging
    )
```

### 2. Use Structured Logging

```python
import logging

logger = logging.getLogger(__name__)

try:
    await operation()
except AgenticBrainError as e:
    logger.error(e.message)           # Brief for operators
    logger.debug(f"Cause: {e.cause}") # Detailed for debugging
    logger.debug(f"Fix: {e.fix}")     # Remediation steps
    logger.debug(f"Debug: {e.debug_info}")  # Context
```

### 3. Provide Context in Debug Info

```python
raise APIError(
    endpoint="/api/chat",
    status_code=500,
    response=response.text,
    original_error=e
)
# debug_info will contain endpoint and status_code for diagnosis
```

### 4. Chain Exceptions for Full Trace

```python
try:
    await inner_operation()
except InnerError as e:
    raise OuterError(...) from e  # Preserves traceback chain
```

## HTTP Error Mapping

When exceptions propagate to API endpoints, they map to appropriate HTTP status codes:

| Exception | HTTP Status |
|-----------|-------------|
| ValidationError | 400 Bad Request |
| AuthenticationError | 401 Unauthorized |
| RateLimitError | 429 Too Many Requests |
| ConfigurationError | 500 Internal Server Error |
| Neo4jConnectionError | 503 Service Unavailable |
| LLMProviderError | 502 Bad Gateway |
| TimeoutError | 504 Gateway Timeout |

## Testing Exception Handling

```python
import pytest
from agentic_brain.exceptions import LLMProviderError

def test_llm_provider_error():
    error = LLMProviderError(
        provider="ollama",
        model="llama3.2",
        original_error=ConnectionError("refused")
    )
    
    assert "ollama" in error.message
    assert error.debug_info["provider"] == "ollama"
    assert error.debug_info["model"] == "llama3.2"
    assert "ollama serve" in error.fix
```

## See Also

- [API Reference](./API.md) - API endpoints and responses
- [Security Guide](./SECURITY.md) - Security error handling
- [Configuration Guide](./CONFIGURATION.md) - Configuration errors
