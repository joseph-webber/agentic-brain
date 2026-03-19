# Integration Tests - Quick Start

## ⚡ Get Started in 30 Seconds

```bash
# Navigate to project
cd /Users/joe/brain/agentic-brain

# Run all integration tests
python3 -m pytest tests/test_imports.py tests/test_integration.py -v
```

✅ **Done!** All 58 tests pass in ~0.1 seconds

---

## 📊 Test Results

```
collected 58 items

tests/test_imports.py::TestPublicImports ... PASSED        [ 10%]
tests/test_imports.py::TestNoCircularImports ... PASSED    [ 12%]
tests/test_imports.py::TestMetadata ... PASSED              [ 13%]
tests/test_imports.py::TestModuleAttributes ... PASSED     [ 15%]
tests/test_imports.py::TestImportPerformance ... PASSED    [ 16%]
tests/test_integration.py::TestFullChatFlow ... PASSED     [ 22%]
tests/test_integration.py::TestSessionPersistence ... PASSED [ 29%]
tests/test_integration.py::TestMemoryStorage ... PASSED    [ 36%]
tests/test_integration.py::TestMultiUserIsolation ... PASSED [ 40%]
tests/test_integration.py::TestErrorHandling ... PASSED    [ 50%]
tests/test_integration.py::TestPerformanceStability ... PASSED [ 61%]
tests/test_integration.py::TestIntegration ... PASSED      [ 70%]
tests/test_integration.py::TestEdgeCases ... PASSED        [ 100%]

======================== 58 passed in 0.07s ========================
```

---

## 🎯 Quick Commands

### Run specific tests

```bash
# Just import tests
pytest tests/test_imports.py -v

# Just integration tests  
pytest tests/test_integration.py -v

# Specific test class
pytest tests/test_integration.py::TestFullChatFlow -v

# Single test
pytest tests/test_integration.py::TestFullChatFlow::test_agent_creation -v
```

### View test details

```bash
# Show which tests are slowest
pytest tests/ -v --durations=10

# Show print statements during tests
pytest tests/ -v -s

# Show full tracebacks on failure
pytest tests/ -v --tb=long
```

### Coverage reporting

```bash
# Generate coverage report
pytest tests/ --cov=agentic_brain

# Generate HTML coverage report
pytest tests/ --cov=agentic_brain --cov-report=html
# Open htmlcov/index.html in browser
```

---

## 🔧 What the Tests Do

### Import Tests (21 tests)
✅ Verify all public imports work  
✅ Check for circular dependencies  
✅ Validate version and metadata  
✅ Test module exports  
✅ Measure import performance  

### Integration Tests (37 tests)
✅ Test agent creation and configuration  
✅ Verify session management  
✅ Test memory initialization (with/without Neo4j)  
✅ Validate multi-user data isolation  
✅ Handle edge cases (unicode, special chars)  
✅ Verify performance characteristics  
✅ Test component integration  

---

## 🎁 Available Fixtures

Use these in your own tests:

```python
# Temporary directory
def test_something(temp_dir):
    path = temp_dir / "myfile.txt"
    path.write_text("content")

# Mock LLM responses
def test_llm(mock_llm):
    response = mock_llm.complete("Hello")
    assert response is not None

# Mock Neo4j
def test_memory(mock_neo4j):
    mock_neo4j.store("data")
    results = mock_neo4j.search("data")

# Environment control
def test_fallback(env_no_neo4j):
    # Test behavior when Neo4j is unavailable
    pass
```

See `conftest.py` for all available fixtures.

---

## 📋 File Structure

```
tests/
├── conftest.py              # 🔧 Fixtures and mocks
├── test_imports.py          # ✓ Import verification (21 tests)
├── test_integration.py      # ✓ Integration tests (37 tests)
├── QUICK_START.md          # 👈 This file
├── README_TESTS.md         # 📋 Quick reference
└── INTEGRATION_TESTS.md    # 📖 Full documentation
```

---

## ✅ Checklist

Before committing changes:

- [ ] Run tests: `pytest tests/test_imports.py tests/test_integration.py -v`
- [ ] All tests pass (should be ~0.1 seconds)
- [ ] No new warnings
- [ ] For new features, add corresponding tests
- [ ] Update documentation if needed

---

## 🆘 Troubleshooting

### Tests are slow?
- Check if Neo4j is running (shouldn't be needed)
- Tests should run in < 0.2 seconds

### Import errors?
```bash
# Make sure you're in the right directory
cd /Users/joe/brain/agentic-brain

# Check Python version (needs 3.9+)
python3 --version

# Reinstall package in development mode
pip install -e .
```

### Specific test failing?
```bash
# Run with verbose output
pytest tests/test_integration.py::TestName::test_method -v -s

# Show full traceback
pytest tests/test_integration.py::TestName::test_method -v --tb=long
```

---

## 📚 Learn More

- **Full docs**: `INTEGRATION_TESTS.md`
- **Quick reference**: `README_TESTS.md`
- **Fixtures**: `conftest.py`
- **Test code**: `test_imports.py`, `test_integration.py`

---

## 🚀 Next Steps

1. ✅ Run the tests
2. ✅ Check everything passes
3. ✅ Read `INTEGRATION_TESTS.md` for details
4. ✅ Add new tests as needed
5. ✅ Integrate into CI/CD pipeline

---

**Questions?** Check the documentation files or the test code itself - it's well-commented!
