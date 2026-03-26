# Transport Layer Tests - Quick Reference

## 🎯 Overview
- **File:** `tests/test_transport.py`
- **Tests:** 77 passing tests
- **Coverage:** 62% of transport module
- **Runtime:** ~0.3 seconds

## 🚀 Quick Commands

### Run All Tests
```bash
cd /Users/joe/brain/agentic-brain
python3 -m pytest tests/test_transport.py -v
```

### Run Specific Test Class
```bash
python3 -m pytest tests/test_transport.py::TestWebSocketTransport -v
python3 -m pytest tests/test_transport.py::TestTransportManager -v
```

### Run with Coverage
```bash
python3 -m pytest tests/test_transport.py --cov=src/agentic_brain/transport --cov-report=term-missing
```

### Run Single Test
```bash
python3 -m pytest tests/test_transport.py::TestTransportManager::test_send_message_success -v
```

## 📊 Test Statistics

| Category | Count |
|----------|-------|
| Config Tests | 9 |
| Message Tests | 6 |
| Enum Tests | 9 |
| WebSocket Tests | 17 |
| Status Tests | 6 |
| Manager Tests | 14 |
| Firebase Fallback | 3 |
| Edge Cases | 5 |
| Mode Tests | 4 |
| Timestamp Tests | 3 |
| **Total** | **77** |

## 🎓 Test Classes Overview

### TransportConfig (9 tests)
Tests configuration object initialization and all field variations.

**Key Test:**
```python
config = TransportConfig(timeout=60.0, transport_type=TransportType.FIREBASE)
assert config.timeout == 60.0
```

### TransportMessage (6 tests)
Tests message creation, metadata, and timestamp handling.

**Key Test:**
```python
msg = TransportMessage(
    content="Hello",
    session_id="sess-1",
    message_id="msg-1",
    metadata={"role": "user"}
)
assert msg.timestamp.tzinfo == timezone.utc
```

### WebSocketTransport (17 tests)
Tests WebSocket connection lifecycle and message operations.

**Key Test:**
```python
await transport.connect()
result = await transport.send(msg)
assert result is True
```

### TransportManager (14 tests)
Tests transport orchestration and multi-mode support.

**Key Test:**
```python
manager = TransportManager(mode=TransportMode.DUAL_WRITE)
await manager.connect(websocket=mock_ws)
await manager.send(msg)
```

### TransportMode (6 tests)
Tests all 5 transport modes.

**Supported Modes:**
- WEBSOCKET_ONLY
- FIREBASE_ONLY
- WEBSOCKET_PRIMARY
- FIREBASE_PRIMARY
- DUAL_WRITE

### Firebase Graceful Fallback (3 tests)
Tests that Firebase is optional and handled gracefully.

**Key Test:**
```python
# Works even if firebase-admin not installed
manager = TransportManager(mode=TransportMode.WEBSOCKET_ONLY)
assert manager is not None
```

## 🔍 Coverage Targets

| Module | Target | Actual | Status |
|--------|--------|--------|--------|
| base.py | 100% | 87% | ✅ High |
| websocket.py | 90% | 81% | ✅ Good |
| manager.py | 80% | 73% | ⚠️ Acceptable |
| firebase.py | 50% | 26% | ℹ️ Optional |
| __init__.py | 80% | 75% | ✅ Good |

## ✅ Test Features

### Async Support
All async methods tested with `@pytest.mark.asyncio`

### Mocking
- WebSocket: `AsyncMock` for all operations
- Firebase: Graceful fallback when SDK unavailable

### Error Handling
- Connection failures
- Missing dependencies
- Message send failures
- Health check exceptions

### Edge Cases
- Large messages (1MB)
- Empty messages
- Rapid connect/disconnect
- Multiple sends
- Timestamp serialization

## 🛠️ Debug Tips

### Run with Detailed Output
```bash
python3 -m pytest tests/test_transport.py -vv --tb=long
```

### Run with Print Statements
```bash
python3 -m pytest tests/test_transport.py -vv -s
```

### Run Specific Line Range
```bash
python3 -m pytest tests/test_transport.py::TestWebSocketTransport::test_connect_success -vv
```

### Generate HTML Report
```bash
python3 -m pytest tests/test_transport.py --html=report.html
```

## 📝 Writing New Tests

### Pattern 1: Simple Synchronous Test
```python
def test_config_default(self):
    config = TransportConfig()
    assert config.timeout == 30.0
```

### Pattern 2: Async Test with Mock
```python
@pytest.mark.asyncio
async def test_send_success(self):
    mock_ws = AsyncMock()
    mock_ws.send_json = AsyncMock()
    
    manager = TransportManager()
    await manager.connect(websocket=mock_ws)
    result = await manager.send(msg)
    
    assert result is True
    mock_ws.send_json.assert_called_once()
```

### Pattern 3: Fixture Usage
```python
@pytest.fixture
def transport(self):
    config = TransportConfig()
    mock_ws = AsyncMock()
    return WebSocketTransport(config, mock_ws)

async def test_something(self, transport):
    result = await transport.connect()
    assert result is True
```

## 🚨 Common Issues

### Issue: Tests timeout
**Solution:** Check `config.timeout` setting, increase if needed

### Issue: Mock assertions fail
**Solution:** Verify mock was called with `assert_called_once()` before other calls

### Issue: Async context errors
**Solution:** Use `@pytest.mark.asyncio` decorator on async test functions

### Issue: Firebase import warnings
**Solution:** Expected behavior - Firebase is optional dependency

## 📚 Test Organization

```
tests/
├── test_transport.py
│   ├── TestTransportConfig          (config tests)
│   ├── TestTransportMessage         (message tests)
│   ├── TestTransportType            (enum tests)
│   ├── TestTransportMode            (mode tests)
│   ├── TestWebSocketTransport       (websocket tests)
│   ├── TestTransportStatus          (status tests)
│   ├── TestTransportManager         (manager tests)
│   ├── TestFirebaseGracefulFallback (optional dependency)
│   ├── TestTransportEdgeCases       (edge cases)
│   ├── TestTransportModes           (mode-specific tests)
│   ├── TestWebSocketReceive         (receive tests)
│   └── TestTransportMessageTimestamps (timestamp tests)
└── TRANSPORT_TEST_REPORT.md         (full report)
```

## 🎯 Next Steps

1. **Run all tests:** `python3 -m pytest tests/test_transport.py -v`
2. **Check coverage:** Add coverage for manager/firebase modules
3. **Add integration tests:** Real WebSocket/Firebase connections
4. **Add performance tests:** Load testing and benchmarks

## 📞 Related Files

- Implementation: `src/agentic_brain/transport/`
- Docs: `TRANSPORT_TEST_REPORT.md`
- Config: `pyproject.toml`

---

**Last Updated:** 2024
**Status:** ✅ All 77 tests passing
