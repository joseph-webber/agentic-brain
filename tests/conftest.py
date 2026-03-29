# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Agentic Brain Contributors
#
# Licensed under the Apache License, Version 2.0 (the "License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0
#
# Unless required by applicable law or agreed to in writing, software
# distributed under the License is distributed on an "AS IS" BASIS,
# WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
# See the License for the specific language governing permissions and
# limitations under the License.

"""
Pytest configuration and fixtures for agentic-brain tests.

Provides robust test infrastructure with:
- Environment detection (CI vs local)
- Auto-skip markers for external services
- Mock fixtures for all external dependencies
- Comprehensive test isolation
"""

import importlib.util
import os
import socket
import sys
import tempfile
from collections.abc import Generator
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock, patch

import pytest

# Import shared fixtures (e.g., mock LLM stubs) so pytest registers them.
from tests.fixtures.mock_llm import (  # noqa: F401  (re-exported fixture)
    mock_llm_requests,
)


def pytest_addoption(parser):
    parser.addoption(
        "--run-integration",
        action="store_true",
        default=False,
        help="Run tests marked as integration (otherwise skipped in CI by default).",
    )
    parser.addoption(
        "--run-e2e",
        action="store_true",
        default=False,
        help="Run tests marked as e2e (otherwise skipped in CI by default).",
    )
    parser.addoption(
        "--run-slow",
        action="store_true",
        default=False,
        help="Run tests marked as slow (otherwise skipped in CI by default).",
    )


def _module_available(module_name: str) -> bool:
    return importlib.util.find_spec(module_name) is not None


def _service_available(env_var: str, module_name: str) -> bool:
    return bool(os.getenv(env_var)) and _module_available(module_name)


def pytest_collection_modifyitems(config, items):
    skip_redis = pytest.mark.skip(reason="Redis not available")
    skip_neo4j = pytest.mark.skip(reason="Neo4j not available")
    skip_temporal = pytest.mark.skip(reason="Temporal not available")
    skip_docker = pytest.mark.skip(reason="Docker not available")
    skip_firebase = pytest.mark.skip(reason="Firebase not available")
    skip_e2e = pytest.mark.skip(reason="E2E tests disabled in CI")
    skip_integration = pytest.mark.skip(reason="Integration tests disabled in CI")
    skip_cultural = pytest.mark.skip(reason="Cultural sensitivity tests disabled in CI")
    skip_demo_refresh = pytest.mark.skip(reason="Demo JWT refresh test disabled in CI")
    skip_infrastructure = pytest.mark.skip(reason="Infrastructure tests disabled in CI")
    skip_installer_enhanced = pytest.mark.skip(
        reason="Installer enhanced tests disabled in CI"
    )

    redis_ok = _service_available("REDIS_HOST", "redis")
    neo4j_ok = _service_available("NEO4J_URI", "neo4j")
    temporal_ok = _service_available("TEMPORAL_HOST", "temporalio")
    docker_ok = _module_available("docker") and bool(os.getenv("DOCKER_HOST"))
    firebase_ok = _module_available("firebase_admin") and bool(
        os.getenv("GOOGLE_APPLICATION_CREDENTIALS")
    )

    for item in items:
        nodeid = item.nodeid.lower()
        path = str(item.fspath).replace("\\", "/").lower()
        path_name = Path(path).name

        if "/tests/e2e/" in path and not item.get_closest_marker("e2e"):
            item.add_marker(pytest.mark.e2e)
        elif "/tests/integration/" in path and not item.get_closest_marker(
            "integration"
        ):
            item.add_marker(pytest.mark.integration)
        elif not any(
            item.get_closest_marker(m) for m in ("unit", "integration", "e2e")
        ):
            item.add_marker(pytest.mark.unit)

        if any(token in path_name for token in ("commerce", "woo", "wordpress")):
            item.add_marker(pytest.mark.commerce)
        if "woo" in path_name:
            item.add_marker(pytest.mark.woocommerce)
        if "wordpress" in path_name or "/wp_" in path:
            item.add_marker(pytest.mark.wordpress)

        if item.get_closest_marker("requires_redis") and not redis_ok:
            item.add_marker(skip_redis)
        if (
            "neo4j" in nodeid or item.get_closest_marker("requires_neo4j")
        ) and not neo4j_ok:
            item.add_marker(skip_neo4j)
        if (
            "temporal" in nodeid or item.get_closest_marker("requires_temporal")
        ) and not temporal_ok:
            item.add_marker(skip_temporal)
        if (
            "docker" in nodeid or item.get_closest_marker("requires_docker")
        ) and not docker_ok:
            item.add_marker(skip_docker)
        if (
            "firebase" in nodeid or item.get_closest_marker("requires_firebase")
        ) and not firebase_ok:
            item.add_marker(skip_firebase)
        if "/e2e/" in path and not os.getenv("CI_RUN_E2E"):
            item.add_marker(skip_e2e)
        if (
            "/integration/" in path or item.get_closest_marker("integration")
        ) and not os.getenv("CI_RUN_INTEGRATION"):
            item.add_marker(skip_integration)
        if "/test_cultural_sensitivity.py" in path and not os.getenv("CI_RUN_CULTURAL"):
            item.add_marker(skip_cultural)
        if "test_refresh_token_works" in nodeid and not os.getenv(
            "CI_RUN_DEMO_REFRESH"
        ):
            item.add_marker(skip_demo_refresh)
        if "/test_infrastructure.py" in path and not os.getenv("CI_RUN_INFRASTRUCTURE"):
            item.add_marker(skip_infrastructure)
        if "/test_installer_enhanced.py" in path and not os.getenv(
            "CI_RUN_INSTALLER_ENHANCED"
        ):
            item.add_marker(skip_installer_enhanced)


# =============================================================================
# ENVIRONMENT DETECTION
# =============================================================================


def is_ci_environment() -> bool:
    """Detect if running in CI environment."""
    ci_indicators = [
        "CI",
        "CONTINUOUS_INTEGRATION",
        "GITHUB_ACTIONS",
        "GITLAB_CI",
        "TRAVIS",
        "CIRCLECI",
        "JENKINS_URL",
        "BUILD_NUMBER",
        "BUILDKITE",
    ]
    return any(os.getenv(var) for var in ci_indicators)


def is_service_available(host: str, port: int, timeout: float = 1.0) -> bool:
    """Check if a service is available on host:port."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (TimeoutError, ConnectionRefusedError, OSError):
        return False


# Global test environment info
IS_CI = is_ci_environment()
REDIS_AVAILABLE = is_service_available("localhost", 6379)
NEO4J_AVAILABLE = is_service_available("localhost", 7687)
TEMPORAL_AVAILABLE = is_service_available("localhost", 7233)


# =============================================================================
# AUTO-SKIP FUNCTIONALITY
# =============================================================================


def pytest_runtest_setup(item):
    """Auto-skip tests based on markers and environment."""
    # Skip CI-marked tests in CI
    if IS_CI and item.get_closest_marker("skip_ci"):
        pytest.skip("Skipped in CI environment")

    run_integration = item.config.getoption("--run-integration")
    run_e2e = item.config.getoption("--run-e2e")
    run_slow = item.config.getoption("--run-slow")

    if IS_CI and item.get_closest_marker("integration") and not run_integration:
        pytest.skip("Integration test skipped in CI environment")
    if IS_CI and item.get_closest_marker("e2e") and not run_e2e:
        pytest.skip("E2E test skipped in CI environment")
    if IS_CI and item.get_closest_marker("slow") and not run_slow:
        pytest.skip("Slow test skipped in CI environment")

    # Skip service-dependent tests if service not available
    if item.get_closest_marker("requires_redis") and not REDIS_AVAILABLE:
        pytest.skip("Redis not available")

    if item.get_closest_marker("requires_neo4j") and not NEO4J_AVAILABLE:
        pytest.skip("Neo4j not available")

    if item.get_closest_marker("requires_temporal") and not TEMPORAL_AVAILABLE:
        pytest.skip("Temporal not available")

    # Docker check
    if item.get_closest_marker("requires_docker"):
        try:
            import docker

            client = docker.from_env()
            client.ping()
        except Exception:
            pytest.skip("Docker not available")

    # Firebase emulator check
    if item.get_closest_marker("requires_firebase"):
        if not (
            is_service_available("localhost", 8080)
            or is_service_available("localhost", 9099)
        ):
            pytest.skip("Firebase emulator not available")


# =============================================================================
# CORE FIXTURES
# =============================================================================


@pytest.fixture(scope="session")
def test_environment():
    """Information about the test environment."""
    return {
        "is_ci": IS_CI,
        "redis_available": REDIS_AVAILABLE,
        "neo4j_available": NEO4J_AVAILABLE,
        "temporal_available": TEMPORAL_AVAILABLE,
    }


@pytest.fixture(autouse=True)
def configure_test_modes(monkeypatch):
    """
    Provide deterministic Groq responses and ensure cultural sensitivity tests
    always run during CI/local test sessions.
    """

    if not os.getenv("GROQ_API_KEY"):
        monkeypatch.setenv("GROQ_API_KEY", "gsk_test_local_key")

    monkeypatch.setenv("GROQ_TEST_MODE", "1")
    monkeypatch.setenv("CI_RUN_CULTURAL", "1")


@pytest.fixture(scope="session")
def skip_without_redis():
    """Skip test if Redis is not available."""
    if not REDIS_AVAILABLE and not os.getenv("REDIS_HOST"):
        pytest.skip("Redis not available - set REDIS_HOST or start Redis server")
    return REDIS_AVAILABLE


@pytest.fixture(scope="session")
def skip_without_neo4j():
    """Skip test if Neo4j is not available."""
    if not NEO4J_AVAILABLE and not os.getenv("NEO4J_URI"):
        pytest.skip("Neo4j not available - set NEO4J_URI or start Neo4j server")
    return NEO4J_AVAILABLE


@pytest.fixture(scope="session")
def skip_without_temporal():
    """Skip test if Temporal is not available."""
    if not TEMPORAL_AVAILABLE and not os.getenv("TEMPORAL_HOST"):
        pytest.skip(
            "Temporal not available - set TEMPORAL_HOST or start Temporal server"
        )
    return TEMPORAL_AVAILABLE


@pytest.fixture
def temp_dir() -> Generator[Path, None, None]:
    """Temporary directory fixture."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture(autouse=True)
def clean_environment(monkeypatch):
    """Clean environment variables between tests."""
    # Clear potentially problematic environment variables
    test_vars = [
        "NEO4J_URI",
        "NEO4J_USER",
        "NEO4J_PASSWORD",
        "REDIS_URL",
        "REDIS_HOST",
        "REDIS_PORT",
        "TEMPORAL_HOST",
        "TEMPORAL_PORT",
        "OPENAI_API_KEY",
        "ANTHROPIC_API_KEY",
        "FIREBASE_SERVICE_ACCOUNT_KEY",
    ]
    for var in test_vars:
        monkeypatch.delenv(var, raising=False)

    yield


@pytest.fixture(autouse=True)
def aioredis_stub(monkeypatch):
    """
    Stub aioredis module to avoid importing the upstream package which is not
    yet compatible with Python 3.14 (duplicate TimeoutError inheritance).
    """

    class _FakeRedis:
        async def ping(self):
            return True

    class _FakeAioredis:
        Redis = _FakeRedis

        @staticmethod
        async def from_url(*args, **kwargs):
            return _FakeRedis()

    monkeypatch.setitem(sys.modules, "aioredis", _FakeAioredis())


# =============================================================================
# LLM MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_llm_response():
    """Mock LLM response function."""

    def _mock_response(prompt: str, model: str = "llama3.1:8b", **kwargs) -> str:
        """Generate a mock LLM response based on prompt."""
        prompt_lower = prompt.lower()

        if "hello" in prompt_lower or "hi" in prompt_lower:
            return "Hello! I'm an AI assistant. How can I help you today?"
        elif "how are you" in prompt_lower:
            return "I'm functioning well, thank you for asking!"
        elif "count to" in prompt_lower:
            return "1. First\n2. Second\n3. Third"
        elif "memory" in prompt_lower or "remember" in prompt_lower:
            return "I'll store that information in my memory for future reference."
        elif "error" in prompt_lower:
            return "I understand there was an error. Let me help troubleshoot."
        elif "analyze" in prompt_lower:
            return "Based on my analysis, here are the key findings:\n1. Issue identified\n2. Solution proposed\n3. Next steps outlined"
        else:
            return f"I understood your message: '{prompt[:50]}...'. How can I assist?"

    return _mock_response


@pytest.fixture
def mock_llm(mock_llm_response):
    """Mock LLM provider fixture."""
    mock = MagicMock()
    mock.complete = MagicMock(side_effect=mock_llm_response)
    mock.chat = MagicMock(
        return_value={"choices": [{"message": {"content": "Mocked response"}}]}
    )
    mock.embeddings = MagicMock(
        return_value={"data": [{"embedding": [0.1, 0.2, 0.3] * 128}]}
    )
    return mock


@pytest.fixture
def mock_openai():
    """Mock OpenAI client."""
    with patch("openai.OpenAI") as mock_client:
        # Mock completion
        mock_completion = MagicMock()
        mock_completion.choices = [
            MagicMock(message=MagicMock(content="Mocked OpenAI response"))
        ]
        mock_client.return_value.chat.completions.create.return_value = mock_completion

        # Mock embeddings
        mock_embedding = MagicMock()
        mock_embedding.data = [MagicMock(embedding=[0.1] * 1536)]
        mock_client.return_value.embeddings.create.return_value = mock_embedding

        yield mock_client.return_value


# =============================================================================
# DATABASE MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_neo4j_driver():
    """Mock Neo4j driver fixture."""
    mock_driver = MagicMock()
    mock_session = MagicMock()

    # Mock session methods
    mock_session.run = MagicMock(return_value=[])
    mock_session.execute_write = MagicMock(return_value=None)
    mock_session.execute_read = MagicMock(return_value=[])
    mock_session.close = MagicMock()

    # Mock result for queries
    mock_result = MagicMock()
    mock_result.single = MagicMock(return_value={"count": 0})
    mock_result.data = MagicMock(return_value=[])
    mock_session.run.return_value = mock_result

    # Mock driver methods
    mock_driver.session = MagicMock(return_value=mock_session)
    mock_driver.verify_connectivity = MagicMock(return_value=None)
    mock_driver.close = MagicMock()

    return mock_driver


@pytest.fixture
def mock_neo4j():
    """Mock Neo4j memory store fixture."""
    mock = MagicMock()

    # Mock methods
    mock.store = AsyncMock(return_value=None)
    mock.retrieve = AsyncMock(return_value=[])
    mock.search = AsyncMock(return_value=[])
    mock.clear = AsyncMock(return_value=None)
    mock.is_available = MagicMock(return_value=True)
    mock.close = AsyncMock(return_value=None)
    mock.health_check = AsyncMock(return_value={"status": "healthy"})

    return mock


@pytest.fixture
def mock_redis():
    """Mock Redis client fixture."""
    mock_redis = MagicMock()

    # Mock Redis methods
    mock_redis.ping = MagicMock(return_value=True)
    mock_redis.get = MagicMock(return_value=None)
    mock_redis.set = MagicMock(return_value=True)
    mock_redis.delete = MagicMock(return_value=1)
    mock_redis.exists = MagicMock(return_value=False)
    mock_redis.expire = MagicMock(return_value=True)
    mock_redis.flushdb = MagicMock(return_value=True)
    mock_redis.close = MagicMock()

    # Mock connection pool
    mock_redis.connection_pool = MagicMock()
    mock_redis.connection_pool.connection_kwargs = {"host": "localhost", "port": 6379}

    return mock_redis


# =============================================================================
# TEMPORAL MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_temporal_client():
    """Mock Temporal client fixture."""
    mock_client = AsyncMock()

    # Mock workflow execution
    mock_handle = AsyncMock()
    mock_handle.result = AsyncMock(return_value="workflow_result")
    mock_handle.query = AsyncMock(return_value="query_result")
    mock_handle.signal = AsyncMock()

    mock_client.start_workflow = AsyncMock(return_value=mock_handle)
    mock_client.get_workflow_handle = AsyncMock(return_value=mock_handle)

    return mock_client


@pytest.fixture
def mock_temporal_worker():
    """Mock Temporal worker fixture."""
    mock_worker = AsyncMock()

    mock_worker.run = AsyncMock()
    mock_worker.shutdown = AsyncMock()

    return mock_worker


# =============================================================================
# API AND TRANSPORT MOCK FIXTURES
# =============================================================================


@pytest.fixture
def mock_firebase_admin():
    """Mock Firebase Admin SDK."""
    with (
        patch("firebase_admin.credentials") as mock_creds,
        patch("firebase_admin.initialize_app"),
        patch("firebase_admin.firestore") as mock_firestore,
        patch("firebase_admin.messaging") as mock_messaging,
    ):

        # Mock credentials
        mock_creds.Certificate.return_value = MagicMock()

        # Mock Firestore
        mock_db = MagicMock()
        mock_collection = MagicMock()
        mock_doc = MagicMock()

        mock_doc.get.return_value = MagicMock(
            exists=True, to_dict=lambda: {"test": "data"}
        )
        mock_doc.set.return_value = None
        mock_collection.document.return_value = mock_doc
        mock_db.collection.return_value = mock_collection
        mock_firestore.client.return_value = mock_db

        # Mock Messaging
        mock_messaging.send.return_value = "mock_message_id"

        yield {
            "credentials": mock_creds,
            "firestore": mock_firestore,
            "messaging": mock_messaging,
        }


@pytest.fixture
def mock_websocket():
    """Mock WebSocket connection."""
    mock_ws = AsyncMock()

    mock_ws.send = AsyncMock()
    mock_ws.recv = AsyncMock(return_value='{"type": "test", "data": {}}')
    mock_ws.close = AsyncMock()
    mock_ws.closed = False

    return mock_ws


# =============================================================================
# IN-MEMORY STORES FOR TESTING
# =============================================================================


@pytest.fixture
def mock_in_memory_store():
    """In-memory store fixture for tests."""
    store = {
        "messages": [],
        "memories": [],
        "sessions": {},
        "workflows": {},
        "agents": {},
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

        def save_workflow(self, workflow_id, workflow_data):
            self.data["workflows"][workflow_id] = workflow_data

        def get_workflow(self, workflow_id):
            return self.data["workflows"].get(workflow_id)

        def clear(self):
            for key in self.data:
                if isinstance(self.data[key], (list, dict)):
                    self.data[key].clear()

    return MockStore(store)


@pytest.fixture
def mock_vector_db():
    """Mock vector database (Pinecone/Weaviate/etc)."""
    mock_db = MagicMock()

    # Mock search results
    mock_result = {
        "matches": [
            {"id": "test_1", "score": 0.95, "metadata": {"text": "Test document 1"}},
            {"id": "test_2", "score": 0.85, "metadata": {"text": "Test document 2"}},
        ]
    }

    mock_db.query = MagicMock(return_value=mock_result)
    mock_db.upsert = MagicMock(return_value={"upserted_count": 1})
    mock_db.delete = MagicMock(return_value=True)
    mock_db.describe_index_stats = MagicMock(return_value={"total_vector_count": 100})

    return mock_db


# =============================================================================
# ENVIRONMENT FIXTURES
# =============================================================================


@pytest.fixture
def env_no_services(monkeypatch):
    """Environment with no external services available."""
    monkeypatch.setenv("NEO4J_URI", "")
    monkeypatch.setenv("REDIS_URL", "")
    monkeypatch.setenv("TEMPORAL_HOST", "")
    monkeypatch.setenv("SERVICES_AVAILABLE", "false")
    return monkeypatch


@pytest.fixture
def env_with_services(monkeypatch):
    """Environment with all services available (mocked)."""
    monkeypatch.setenv("NEO4J_URI", os.getenv("NEO4J_URI", "bolt://localhost:7687"))
    monkeypatch.setenv("NEO4J_USER", os.getenv("NEO4J_USER", "neo4j"))
    monkeypatch.setenv("NEO4J_PASSWORD", os.getenv("NEO4J_PASSWORD", "password"))
    monkeypatch.setenv("REDIS_URL", os.getenv("REDIS_URL", "redis://localhost:6379"))
    monkeypatch.setenv("REDIS_PASSWORD", os.getenv("REDIS_PASSWORD", "testpass"))
    monkeypatch.setenv("TEMPORAL_HOST", os.getenv("TEMPORAL_HOST", "localhost:7233"))
    monkeypatch.setenv("SERVICES_AVAILABLE", "true")
    return monkeypatch


@pytest.fixture
def env_ci(monkeypatch):
    """Simulate CI environment."""
    monkeypatch.setenv("CI", "true")
    monkeypatch.setenv("GITHUB_ACTIONS", "true")
    return monkeypatch


# =============================================================================
# CLEANUP AND RESET
# =============================================================================


@pytest.fixture(autouse=True)
def reset_imports():
    """Reset module imports between tests to avoid side effects."""
    yield
    # Cleanup happens naturally with pytest


@pytest.fixture(autouse=True)
def isolate_tests(monkeypatch):
    """Ensure test isolation by mocking external calls."""
    # Mock network calls that might happen during imports
    with (
        patch("requests.get") as mock_get,
        patch("requests.post") as mock_post,
        patch("aiohttp.ClientSession") as mock_session,
    ):

        # Default responses
        mock_response = MagicMock()
        mock_response.json.return_value = {"status": "ok"}
        mock_response.status_code = 200
        mock_response.raise_for_status.return_value = None

        mock_get.return_value = mock_response
        mock_post.return_value = mock_response

        # Mock async session
        mock_async_response = AsyncMock()
        mock_async_response.json.return_value = {"status": "ok"}
        mock_async_response.status = 200

        mock_session_instance = AsyncMock()
        mock_session_instance.get.return_value.__aenter__.return_value = (
            mock_async_response
        )
        mock_session_instance.post.return_value.__aenter__.return_value = (
            mock_async_response
        )
        mock_session.return_value = mock_session_instance

        yield


# =============================================================================
# PERFORMANCE AND DEBUGGING
# =============================================================================


@pytest.fixture
def benchmark_fixture():
    """Fixture for performance benchmarking in tests."""
    import time

    class Benchmark:
        def __init__(self):
            self.start_time = None
            self.end_time = None

        def start(self):
            self.start_time = time.time()

        def end(self):
            self.end_time = time.time()

        @property
        def duration(self):
            if self.start_time and self.end_time:
                return self.end_time - self.start_time
            return None

    return Benchmark()


@pytest.fixture
def debug_mode():
    """Enable debug mode for tests."""
    original_level = os.getenv("LOG_LEVEL", "INFO")
    os.environ["LOG_LEVEL"] = "DEBUG"
    yield
    os.environ["LOG_LEVEL"] = original_level


# =============================================================================
# VOICE SYSTEM FIXTURES
# =============================================================================


@pytest.fixture(autouse=True)
def voice_cleanup():
    """Clean up voice singletons between tests, preventing speech leaking across tests."""
    yield
    # Clear voice queue after each test
    try:
        from agentic_brain.voice.queue import VoiceQueue

        queue = VoiceQueue.get_instance()
        queue.reset()
    except Exception:
        pass

    # Stop daemon (don't just null it — stop it so in-flight speech drains first)
    try:
        import asyncio

        import agentic_brain.voice.resilient as resilient

        if resilient._daemon_instance is not None:
            try:
                loop = asyncio.get_event_loop()
                if loop.is_running():
                    loop.create_task(resilient._daemon_instance.stop())
                else:
                    loop.run_until_complete(resilient._daemon_instance.stop())
            except Exception:
                pass
            resilient._daemon_instance = None
    except Exception:
        pass

    # Wait for serializer to drain then reset, so no queued speech leaks into
    # the next test
    try:
        from agentic_brain.voice.serializer import get_voice_serializer

        serializer = get_voice_serializer()
        serializer.wait_until_idle(timeout=5)
        serializer.reset()
        serializer.set_pause_between(0.3)
        serializer._audit_enabled = True
        serializer._redis_queue = None
    except Exception:
        pass
