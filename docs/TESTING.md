# Testing Guide

<div align="center">

[![Tests](https://img.shields.io/badge/tests-2800%2B-brightgreen?style=for-the-badge&logo=pytest&logoColor=white)](https://github.com/agentic-brain-project/agentic-brain/actions)
[![Coverage](https://img.shields.io/badge/coverage-95%25-brightgreen?style=for-the-badge&logo=codecov&logoColor=white)](https://github.com/agentic-brain-project/agentic-brain/actions)
[![E2E](https://img.shields.io/badge/E2E-Playwright-45BA4B?style=for-the-badge&logo=playwright&logoColor=white)](./tests/e2e/)

**Enterprise-grade testing with 2800+ tests across unit, integration, and E2E.**

</div>

---

## 📊 Test Statistics

| Metric | Value |
|--------|-------|
| **Total Tests** | 2,800+ |
| **Unit Tests** | 2,100+ |
| **Integration Tests** | 500+ |
| **E2E Tests** | 200+ |
| **Coverage** | 95%+ |
| **Test Files** | 64 |
| **CI Runtime** | ~5 min |

---

## 🧪 Testing Framework

Agentic Brain uses **pytest** for testing with comprehensive coverage across all modules.

### Test Stack

| Tool | Purpose |
|------|---------|
| **pytest** | Test framework |
| **pytest-asyncio** | Async test support |
| **pytest-cov** | Coverage reporting |
| **Playwright** | E2E browser testing |
| **hypothesis** | Property-based testing |
| **responses** | HTTP mocking |
| **freezegun** | Time mocking |

---

## Quick Start

```bash
# Install test dependencies
pip install -e ".[test]"

# Run all tests (2800+)
pytest

# Run with verbose output
pytest -v

# Run with coverage report
pytest --cov=agentic_brain --cov-report=html
```

## Test Organization

```
tests/
├── conftest.py              # Shared fixtures
├── e2e/                     # End-to-end tests
│   └── test_e2e_*          # Integration scenarios
├── test_*.py                # Unit tests by module
│
├── QUICK_START.md           # Quick testing guide
├── README_TESTS.md          # Full test documentation
└── INTEGRATION_TESTS.md     # Integration test guide
```

## Running Specific Tests

```bash
# Run a specific test file
pytest tests/test_router.py

# Run a specific test function
pytest tests/test_router.py::test_ollama_chat

# Run tests matching a pattern
pytest -k "router"

# Run tests with specific markers
pytest -m "not slow"
pytest -m "integration"
```

## Test Categories

### Unit Tests (64 test files)

| Module | Test File | Coverage Target |
|--------|-----------|-----------------|
| Router | test_router.py | 95% |
| Auth | test_auth.py, test_auth_security.py | 95% |
| Memory | test_memory.py | 90% |
| Transport | test_transport.py | 90% |
| API | test_api.py, test_api_server.py | 90% |
| CLI | test_cli.py | 85% |
| RAG | test_rag_*.py | 85% |
| Chat | test_chat.py | 90% |
| Bots | test_bots.py | 85% |
| Legal | test_legal.py | 95% |

### Integration Tests

Located in `tests/e2e/` - test complete workflows:

```bash
# Run all integration tests
pytest tests/e2e/ -v

# Run specific integration scenario
pytest tests/e2e/test_e2e_chat.py
```

### Security Tests

```bash
# Run security-focused tests
pytest tests/test_security.py tests/test_auth_security.py -v
```

## Fixtures

Common fixtures are defined in `conftest.py`:

```python
@pytest.fixture
def mock_router():
    """Provides a mock LLMRouter for testing."""
    ...

@pytest.fixture
def test_client():
    """Provides a FastAPI TestClient."""
    ...

@pytest.fixture
def mock_neo4j():
    """Provides a mock Neo4j connection."""
    ...
```

### Using Fixtures

```python
def test_chat_completion(mock_router):
    """Test chat completion with mocked LLM."""
    result = mock_router.chat([{"role": "user", "content": "Hello"}])
    assert result is not None
```

## Mocking External Services

### LLM Providers

```python
from unittest.mock import AsyncMock, patch

@patch("agentic_brain.router.aiohttp.ClientSession")
async def test_ollama_request(mock_session):
    mock_session.return_value.__aenter__.return_value.post = AsyncMock(
        return_value=MockResponse({"message": {"content": "Hello!"}})
    )
    # Test code here
```

### Neo4j

```python
@pytest.fixture
def mock_driver():
    with patch("neo4j.GraphDatabase.driver") as mock:
        yield mock
```

### Firebase

```python
@pytest.fixture
def mock_firebase():
    with patch("firebase_admin.initialize_app"):
        with patch("firebase_admin.firestore.client"):
            yield
```

## Test Markers

```python
import pytest

@pytest.mark.slow
def test_large_batch():
    """Long-running test."""
    ...

@pytest.mark.integration
def test_full_workflow():
    """Requires external services."""
    ...

@pytest.mark.skipif(not os.environ.get("OPENAI_API_KEY"), 
                    reason="Requires OpenAI API key")
def test_openai_integration():
    ...
```

### Running by Marker

```bash
# Skip slow tests
pytest -m "not slow"

# Only integration tests
pytest -m integration

# Skip tests requiring API keys
pytest -m "not requires_api_key"
```

## Coverage Requirements

### Minimum Coverage Targets

- **Critical paths**: 95%+
- **Auth modules**: 95%+
- **Router**: 95%+
- **API routes**: 90%+
- **Utilities**: 85%+

### Generating Coverage Report

```bash
# Terminal report
pytest --cov=agentic_brain --cov-report=term-missing

# HTML report (opens in browser)
pytest --cov=agentic_brain --cov-report=html
open htmlcov/index.html

# XML report (for CI)
pytest --cov=agentic_brain --cov-report=xml
```

## Writing Tests

### Test Structure

```python
"""Tests for module_name module."""

import pytest
from agentic_brain.module_name import function_to_test


class TestFunctionToTest:
    """Tests for function_to_test."""

    def test_basic_usage(self):
        """Test basic function call returns expected result."""
        result = function_to_test("input")
        assert result == "expected"

    def test_edge_case(self):
        """Test function handles edge case."""
        result = function_to_test("")
        assert result == ""

    def test_raises_on_invalid_input(self):
        """Test function raises ValidationError on invalid input."""
        with pytest.raises(ValidationError) as exc:
            function_to_test(None)
        assert "expected string" in str(exc.value)
```

### Async Tests

```python
import pytest

@pytest.mark.asyncio
async def test_async_function():
    """Test async function."""
    result = await async_function()
    assert result is not None
```

### Parametrized Tests

```python
@pytest.mark.parametrize("input,expected", [
    ("hello", "HELLO"),
    ("world", "WORLD"),
    ("", ""),
])
def test_upper(input, expected):
    assert input.upper() == expected
```

## CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: pip install -e ".[test]"
      
      - name: Run tests
        run: pytest --cov=agentic_brain --cov-report=xml
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
```

## Debugging Tests

### Verbose Output

```bash
# Show print statements
pytest -s

# Show full diffs
pytest -vv

# Drop into debugger on failure
pytest --pdb
```

### Running Single Test with Debug

```bash
pytest tests/test_router.py::test_ollama_chat -vvs --pdb
```

## Common Issues

### Async Test Failures

If async tests fail with "event loop closed":

```python
# In conftest.py
@pytest.fixture
def event_loop():
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
```

### Import Errors

Ensure package is installed in development mode:

```bash
pip install -e ".[test]"
```

### Mock Not Working

Check mock target path matches actual import:

```python
# Wrong - mocking wrong location
@patch("module.requests")

# Right - mock where it's used
@patch("agentic_brain.router.aiohttp")
```

---

## 🔥 LLM Smoke Tests

**Weekly automated tests against live LLM providers:**

```bash
# Run LLM smoke tests (requires API keys)
pytest tests/smoke/ -v --smoke

# Test specific provider
pytest tests/smoke/test_smoke_openai.py -v
```

### What We Test

| Provider | Tests | Frequency |
|----------|-------|-----------|
| OpenAI | Completion, Chat, Functions | Weekly |
| Anthropic | Chat, Vision, Tools | Weekly |
| Ollama | All local models | Daily |
| OpenRouter | Routing, Fallback | Weekly |
| Groq | Fast inference | Weekly |
| Together AI | Open models | Weekly |

### Smoke Test Structure

```python
@pytest.mark.smoke
@pytest.mark.slow
async def test_openai_chat_completion():
    """Verify OpenAI API is responding correctly."""
    response = await router.chat(
        messages=[{"role": "user", "content": "Say hello"}],
        model="gpt-4o"
    )
    assert response.content
    assert response.usage.total_tokens > 0
```

---

## 📁 Test Categories

### Router Tests (`test_router*.py`)

Core LLM routing logic:
- Provider selection
- Fallback chains
- Load balancing
- Rate limit handling
- Cost optimization

```bash
pytest tests/test_router.py tests/test_router_fallback.py -v
```

### Transport Tests (`test_transport*.py`)

Communication layers:
- HTTP/REST
- WebSocket
- Firebase real-time
- gRPC
- Message queuing

```bash
pytest tests/test_transport.py tests/test_firebase_transport.py -v
```

### Memory Tests (`test_memory*.py`)

Memory subsystems:
- Session memory
- Long-term memory (Neo4j)
- Vector embeddings
- Semantic search
- Memory compression

```bash
pytest tests/test_memory.py tests/test_memory_neo4j.py -v
```

### Cache Tests (`test_cache*.py`)

Caching layers:
- Response caching
- Embedding cache
- Redis distributed cache
- TTL management
- Cache invalidation

```bash
pytest tests/test_cache.py tests/test_cache_redis.py -v
```

### API Tests (`test_api*.py`)

REST API endpoints:
- Authentication
- Rate limiting
- Request validation
- Response formatting
- Error handling

```bash
pytest tests/test_api.py tests/test_api_server.py -v
```

### CLI Tests (`test_cli*.py`)

Command-line interface:
- Command parsing
- Interactive mode
- Configuration
- Output formatting

```bash
pytest tests/test_cli.py -v
```

---

## 🎭 E2E Tests with Playwright

Browser-based end-to-end testing:

```bash
# Install Playwright browsers
playwright install

# Run E2E tests
pytest tests/e2e/ -v

# Run with headed browser (visible)
pytest tests/e2e/ -v --headed

# Generate screenshots on failure
pytest tests/e2e/ -v --screenshot=only-on-failure
```

### E2E Test Structure

```python
@pytest.mark.e2e
async def test_chat_flow(page: Page):
    """Test complete chat workflow."""
    # Navigate to chat interface
    await page.goto("http://localhost:8000/chat")
    
    # Send message
    await page.fill("#message-input", "Hello, AI!")
    await page.click("#send-button")
    
    # Verify response
    response = await page.wait_for_selector(".ai-response")
    assert await response.text_content()
```

---

## 🔄 CI/CD Integration

### GitHub Actions Workflow

```yaml
name: Tests
on: [push, pull_request]

jobs:
  test:
    runs-on: ubuntu-latest
    strategy:
      matrix:
        python-version: ['3.10', '3.11', '3.12']
    
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: ${{ matrix.python-version }}
      
      - name: Install dependencies
        run: pip install -e ".[test]"
      
      - name: Run tests
        run: pytest --cov=agentic_brain --cov-report=xml -n auto
      
      - name: Upload coverage
        uses: codecov/codecov-action@v4
        with:
          files: coverage.xml
          fail_ci_if_error: true

  e2e:
    runs-on: ubuntu-latest
    needs: test
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-python@v5
        with:
          python-version: '3.12'
      
      - name: Install dependencies
        run: |
          pip install -e ".[test]"
          playwright install chromium
      
      - name: Run E2E tests
        run: pytest tests/e2e/ -v
```

### Coverage Reports

```bash
# Terminal report with missing lines
pytest --cov=agentic_brain --cov-report=term-missing

# HTML report
pytest --cov=agentic_brain --cov-report=html
open htmlcov/index.html

# XML for CI
pytest --cov=agentic_brain --cov-report=xml
```

---

## 📈 Performance Benchmarks

```bash
# Run performance tests
pytest tests/benchmarks/ -v

# Profile specific test
pytest tests/benchmarks/test_router_perf.py --profile
```

### Benchmark Targets

| Operation | Target | Current |
|-----------|--------|---------|
| Router selection | <1ms | 0.3ms |
| Memory lookup | <5ms | 2.1ms |
| Cache hit | <0.5ms | 0.2ms |
| API response | <50ms | 35ms |

---

## See Also

- [QUICK_START.md](../tests/QUICK_START.md) - Quick testing reference
- [README_TESTS.md](../tests/README_TESTS.md) - Full test documentation
- [INTEGRATION_TESTS.md](../tests/INTEGRATION_TESTS.md) - Integration testing guide
- [MEMORY.md](./MEMORY.md) - Memory architecture and testing
