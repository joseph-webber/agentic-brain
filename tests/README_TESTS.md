# Integration Tests - Quick Reference

## Summary
✅ **58 tests** | ✅ **0.08s runtime** | ✅ **100% pass rate** | ✅ **No external dependencies**

## Files Created

```
tests/
├── conftest.py                 # 🔧 Pytest fixtures and mocks
├── test_imports.py             # ✓ Import verification (21 tests)
├── test_integration.py         # ✓ End-to-end tests (37 tests)
└── INTEGRATION_TESTS.md        # 📖 Full documentation
```

## Quick Start

```bash
cd /Users/joe/brain/agentic-brain

# Run all integration tests
python3 -m pytest tests/test_imports.py tests/test_integration.py -v

# Run with timing
python3 -m pytest tests/ -v --durations=10

# Run specific test class
python3 -m pytest tests/test_integration.py::TestFullChatFlow -v

# Run with coverage
python3 -m pytest tests/ --cov=agentic_brain
```

## Test Categories

### Import Tests (21 tests)
- ✓ Public imports work
- ✓ No circular dependencies  
- ✓ Version accessible
- ✓ All exports available

### Integration Tests (37 tests)

**Full Chat Flow** (4 tests)
- Agent creation
- Agent with config
- Message exchange
- Properties verification

**Session Persistence** (4 tests)
- Session creation
- Timestamp tracking
- Multi-agent isolation
- Name persistence

**Memory Storage** (5 tests)
- DataScope enum values
- Initialization without Neo4j
- InMemoryStore fallback
- Proper scoping

**Multi-User Isolation** (3 tests)
- Independent agents
- Scope isolation logic
- Customer ID handling

**Error Handling** (6 tests)
- Empty/special/long names
- Unicode support
- Invalid input handling
- Graceful degradation

**Performance** (4 tests)
- Agent creation time
- Multiple agent creation
- Scope enumeration
- Property access speed

**Integration** (5 tests)
- All components together
- Config preservation
- System prompt storage
- Audio/LLM configuration

**Edge Cases** (6 tests)
- Unicode names (emoji, Chinese, Greek)
- Whitespace handling
- Newlines in names
- Config immutability

## Available Fixtures

```python
def test_example(temp_dir, mock_llm, mock_neo4j, env_no_neo4j):
    # Use fixtures as needed
    path = temp_dir / "file.txt"
    response = mock_llm.complete("prompt")
    mock_neo4j.store("data")
```

### Fixture Reference

| Fixture | Purpose | Usage |
|---------|---------|-------|
| `temp_dir` | Temporary directory | `path = temp_dir / "file"` |
| `mock_llm_response` | LLM response callable | `response = mock_llm_response("prompt")` |
| `mock_llm` | Mocked LLM provider | `mock_llm.complete(...)` |
| `mock_neo4j_driver` | Mocked Neo4j driver | `driver.session()` |
| `mock_neo4j` | Mocked memory store | `mock_neo4j.store(...)` |
| `mock_in_memory_store` | Dict-based store | `store.add_message()` |
| `env_no_neo4j` | Neo4j unavailable | `# Neo4j not available` |
| `env_with_neo4j` | Neo4j available | `# Neo4j available` |

## Performance Metrics

- **Total runtime**: 0.08 seconds ✅
- **Agent creation**: < 100ms
- **50 agents creation**: < 1 second
- **10,000 property accesses**: < 100ms
- **Import timing**: < 1 second

## What's Tested ✅

- Core API stability
- Agent creation and configuration
- Multi-agent isolation
- Memory system initialization
- DataScope enforcement
- Error handling (edge cases)
- Performance characteristics
- Unicode and special character support

## What's NOT Tested

- Actual LLM API calls (mocked)
- Real Neo4j connections (mocked)
- Audio/voice output (mocked)
- Network operations

See `test_chat.py`, `test_memory.py` for end-to-end tests with real services.

## Running in CI/CD

```yaml
# GitHub Actions
- name: Run integration tests
  run: |
    cd agentic-brain
    python3 -m pytest tests/test_imports.py tests/test_integration.py -v

# Jenkins
stage('Test') {
  steps {
    sh 'cd agentic-brain && python3 -m pytest tests/ -v'
  }
}
```

## Common Commands

```bash
# Run all tests
pytest tests/test_imports.py tests/test_integration.py -v

# Run specific test
pytest tests/test_integration.py::TestFullChatFlow::test_agent_creation -v

# Run with verbose output
pytest tests/ -v -s

# Run with coverage report
pytest tests/ --cov=agentic_brain --cov-report=html

# Run failing tests first
pytest tests/ --lf

# Show slowest 10 tests
pytest tests/ --durations=10

# Run with markers
pytest tests/ -m "not slow"
```

## Test Structure

Each test file follows this pattern:

```python
"""Module docstring with purpose and overview."""

import pytest
from unittest.mock import patch, MagicMock

class TestCategory:
    """Logical grouping of related tests."""
    
    def test_specific_behavior(self, fixture_name):
        """Test description following Given-When-Then pattern."""
        # Setup
        obj = SomeClass()
        
        # Execute
        result = obj.do_something()
        
        # Assert
        assert result == expected_value
```

## Debugging Tests

```bash
# Run with full traceback
pytest tests/ -v --tb=long

# Run with print statements
pytest tests/ -v -s

# Run single test with print output
pytest tests/test_integration.py::TestFullChatFlow::test_agent_creation -v -s

# Run with debugging
pytest tests/ --pdb  # drops to pdb on failure
```

## Dependencies

- Python >= 3.9
- pytest >= 8.0.0
- unittest.mock (stdlib)

No external services required! 🚀

## Maintenance

When updating agentic-brain:
1. ✅ Run tests before committing
2. ✅ Add tests for new features
3. ✅ Keep tests fast (< 5 seconds)
4. ✅ Update conftest.py if adding mocks
5. ✅ Document in INTEGRATION_TESTS.md

## Documentation

Full documentation in: `tests/INTEGRATION_TESTS.md`

- Overview of all test classes
- Detailed test descriptions
- Fixture reference
- CI/CD integration examples
- Maintenance notes
