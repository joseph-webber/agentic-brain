"""
Pytest configuration and fixtures for agentic-brain integration tests.

Provides fixtures for:
- Temporary directories
- Mock LLM responses
- Mock Neo4j connections
"""

import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch, AsyncMock
from typing import Generator


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """
    Temporary directory fixture.
    
    Yields:
        Path to temporary directory that is cleaned up after test.
    """
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_llm_response():
    """
    Mock LLM response function.
    
    Returns a callable that generates mock responses.
    """
    def _mock_response(
        prompt: str,
        model: str = "llama3.1:8b",
        **kwargs
    ) -> str:
        """Generate a mock LLM response based on prompt."""
        # Simple mock logic - echo back a structured response
        prompt_lower = prompt.lower()
        
        if "hello" in prompt_lower or "hi" in prompt_lower:
            return "Hello! I'm an AI assistant. How can I help you today?"
        elif "how are you" in prompt_lower:
            return "I'm functioning well, thank you for asking!"
        elif "count to" in prompt_lower:
            # Extract number if present
            return "1. First\n2. Second\n3. Third"
        elif "memory" in prompt_lower or "remember" in prompt_lower:
            return "I'll store that information in my memory for future reference."
        else:
            return f"I understood your message: '{prompt[:50]}...'. How can I assist?"
    
    return _mock_response


@pytest.fixture
def mock_llm(mock_llm_response):
    """
    Mock LLM provider fixture.
    
    Returns a MagicMock that simulates OpenAI/LLM API.
    """
    mock = MagicMock()
    mock.complete = MagicMock(side_effect=mock_llm_response)
    mock.chat = MagicMock(
        return_value={"choices": [{"message": {"content": "Mocked response"}}]}
    )
    return mock


@pytest.fixture
def mock_neo4j_driver():
    """
    Mock Neo4j driver fixture.
    
    Returns a MagicMock that simulates Neo4j connection.
    """
    mock_driver = MagicMock()
    mock_session = MagicMock()
    
    # Mock session methods
    mock_session.run = MagicMock(return_value=[])
    mock_session.execute_write = MagicMock(return_value=None)
    mock_session.execute_read = MagicMock(return_value=[])
    mock_session.close = MagicMock()
    
    # Mock driver methods
    mock_driver.session = MagicMock(return_value=mock_session)
    mock_driver.verify_connectivity = MagicMock(return_value=None)
    mock_driver.close = MagicMock()
    
    return mock_driver


@pytest.fixture
def mock_neo4j():
    """
    Mock Neo4j memory store fixture.
    
    Returns a MagicMock that simulates Neo4jMemory interface.
    """
    mock = MagicMock()
    
    # Mock methods
    mock.store = MagicMock(return_value=None)
    mock.retrieve = MagicMock(return_value=[])
    mock.search = MagicMock(return_value=[])
    mock.clear = MagicMock(return_value=None)
    mock.is_available = MagicMock(return_value=True)
    mock.close = MagicMock(return_value=None)
    
    return mock


@pytest.fixture
def mock_in_memory_store():
    """
    In-memory store fixture for tests.
    
    Returns a simple dict-based store implementation.
    """
    store = {
        "messages": [],
        "memories": [],
        "sessions": {},
    }
    
    class MockStore:
        def __init__(self, data):
            self.data = data
        
        def add_message(self, msg):
            self.data["messages"].append(msg)
            return msg
        
        def get_messages(self):
            return self.data["messages"]
        
        def add_memory(self, mem):
            self.data["memories"].append(mem)
            return mem
        
        def get_memories(self):
            return self.data["memories"]
        
        def save_session(self, session_id, session_data):
            self.data["sessions"][session_id] = session_data
        
        def load_session(self, session_id):
            return self.data["sessions"].get(session_id)
        
        def clear(self):
            self.data["messages"].clear()
            self.data["memories"].clear()
            self.data["sessions"].clear()
    
    return MockStore(store)


@pytest.fixture(autouse=True)
def reset_imports():
    """
    Reset module imports between tests to avoid side effects.
    
    This runs automatically before each test.
    """
    yield
    # Cleanup happens naturally with pytest, but this ensures
    # no test-specific state leaks to the next test


@pytest.fixture
def env_no_neo4j(monkeypatch):
    """
    Fixture that simulates Neo4j being unavailable.
    
    Use this to test graceful degradation when Neo4j is not running.
    """
    monkeypatch.setenv("NEO4J_URI", "")
    monkeypatch.setenv("NEO4J_AVAILABLE", "false")
    return monkeypatch


@pytest.fixture
def env_with_neo4j(monkeypatch):
    """
    Fixture that simulates Neo4j being available.
    
    Use this to test Neo4j integration (with mocking).
    """
    monkeypatch.setenv("NEO4J_URI", "bolt://localhost:7687")
    monkeypatch.setenv("NEO4J_USER", "neo4j")
    monkeypatch.setenv("NEO4J_PASSWORD", "password")
    monkeypatch.setenv("NEO4J_AVAILABLE", "true")
    return monkeypatch
