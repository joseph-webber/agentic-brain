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
Tests for connection pooling.

Tests for:
- Neo4j pool creation and management
- HTTP pool creation and management
- Pool manager lifecycle
- Connection acquisition and release
- Circuit breaker behavior
- Health checks
- Graceful shutdown
"""

from unittest.mock import MagicMock, patch

import pytest

# ============================================================================
# Neo4j Pool Tests
# ============================================================================


class TestNeo4jPoolConfig:
    """Tests for Neo4jPoolConfig."""

    def test_default_values(self, monkeypatch):
        """Test default configuration values."""
        # Clear env vars that would override defaults
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("NEO4J_USER", raising=False)
        from agentic_brain.pooling.neo4j_pool import Neo4jPoolConfig

        config = Neo4jPoolConfig()

        assert config.uri == "bolt://localhost:7687"
        assert config.user == "neo4j"
        assert config.password == ""
        assert config.database == "neo4j"
        assert config.max_connections == 50
        assert config.min_connections == 5
        assert config.connection_timeout == 30.0
        assert config.max_lifetime == 3600.0

    def test_custom_values(self, monkeypatch):
        """Test custom configuration values."""
        # Clear env vars that would override custom values
        monkeypatch.delenv("NEO4J_URI", raising=False)
        monkeypatch.delenv("NEO4J_USER", raising=False)
        monkeypatch.delenv("NEO4J_PASSWORD", raising=False)
        from agentic_brain.pooling.neo4j_pool import Neo4jPoolConfig

        config = Neo4jPoolConfig(
            uri="bolt://custom:7687",
            user="custom_user",
            password="secret",
            max_connections=100,
        )

        assert config.uri == "bolt://custom:7687"
        assert config.user == "custom_user"
        assert config.password == "secret"
        assert config.max_connections == 100

    def test_env_override(self, monkeypatch):
        """Test environment variable override."""
        from agentic_brain.pooling.neo4j_pool import Neo4jPoolConfig

        monkeypatch.setenv("NEO4J_URI", "bolt://env:7687")
        monkeypatch.setenv("NEO4J_USER", "env_user")
        monkeypatch.setenv("NEO4J_PASSWORD", "env_pass")
        monkeypatch.setenv("NEO4J_POOL_SIZE", "200")
        monkeypatch.setenv("CONNECTION_TIMEOUT", "60")

        config = Neo4jPoolConfig()

        assert config.uri == "bolt://env:7687"
        assert config.user == "env_user"
        assert config.password == "env_pass"
        assert config.max_connections == 200
        assert config.connection_timeout == 60.0


class TestPoolMetrics:
    """Tests for PoolMetrics."""

    def test_initial_values(self):
        """Test initial metric values."""
        from agentic_brain.pooling.neo4j_pool import PoolMetrics

        metrics = PoolMetrics()

        assert metrics.active_connections == 0
        assert metrics.idle_connections == 0
        assert metrics.total_acquisitions == 0
        assert metrics.failed_acquisitions == 0

    def test_record_acquisition(self):
        """Test recording acquisition metrics."""
        from agentic_brain.pooling.neo4j_pool import PoolMetrics

        metrics = PoolMetrics()

        metrics.record_acquisition(10.0)
        metrics.record_acquisition(20.0)
        metrics.record_acquisition(30.0)

        assert metrics.total_acquisitions == 3
        assert metrics.average_acquisition_time == 20.0


class TestNeo4jPool:
    """Tests for Neo4jPool."""

    def test_pool_initialization(self):
        """Test pool initialization."""
        from agentic_brain.pooling.neo4j_pool import Neo4jPool, Neo4jPoolConfig

        config = Neo4jPoolConfig(max_connections=25)
        pool = Neo4jPool(config)

        assert pool.config.max_connections == 25
        assert not pool.is_started

    @pytest.mark.asyncio
    async def test_startup_without_neo4j(self):
        """Test startup fails gracefully without neo4j package."""
        from agentic_brain.pooling.neo4j_pool import Neo4jPool

        pool = Neo4jPool()

        with patch.dict("sys.modules", {"neo4j": None}):
            with pytest.raises(ImportError):
                await pool.startup()

    @pytest.mark.asyncio
    async def test_startup_with_mock_driver(self):
        """Test startup with mocked Neo4j driver."""
        from agentic_brain.pooling.neo4j_pool import Neo4jPool, Neo4jPoolConfig

        config = Neo4jPoolConfig(password="test")
        pool = Neo4jPool(config)

        mock_driver = MagicMock()
        mock_driver.verify_connectivity = MagicMock()

        with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
            await pool.startup()

            assert pool.is_started

            await pool.shutdown()
            assert not pool.is_started

    @pytest.mark.asyncio
    async def test_acquire_without_startup(self):
        """Test acquiring connection without startup raises error."""
        from agentic_brain.pooling.neo4j_pool import Neo4jPool

        pool = Neo4jPool()

        with pytest.raises(RuntimeError, match="not started"):
            async with pool.acquire():
                pass

    @pytest.mark.asyncio
    async def test_connection_acquisition_metrics(self):
        """Test that connection acquisition updates metrics."""
        from agentic_brain.pooling.neo4j_pool import Neo4jPool, Neo4jPoolConfig

        config = Neo4jPoolConfig(password="test")
        pool = Neo4jPool(config)

        mock_driver = MagicMock()
        mock_driver.verify_connectivity = MagicMock()

        with patch("neo4j.GraphDatabase.driver", return_value=mock_driver):
            await pool.startup()

            async with pool.acquire():
                assert pool.metrics.active_connections == 1

            assert pool.metrics.total_releases == 1
            assert pool.metrics.total_acquisitions == 1

            await pool.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_not_started(self):
        """Test health check when pool not started."""
        from agentic_brain.pooling.neo4j_pool import Neo4jPool

        pool = Neo4jPool()
        health = await pool.health_check()

        assert health["healthy"] is False
        assert health["connected"] is False

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self):
        """Test that shutdown can be called multiple times."""
        from agentic_brain.pooling.neo4j_pool import Neo4jPool

        pool = Neo4jPool()

        # Should not raise
        await pool.shutdown()
        await pool.shutdown()


class TestDirectNeo4jConnection:
    """Tests for DirectNeo4jConnection fallback."""

    def test_initialization(self):
        """Test direct connection initialization."""
        from agentic_brain.pooling.neo4j_pool import DirectNeo4jConnection

        conn = DirectNeo4jConnection(
            uri="bolt://localhost:7687",
            user="neo4j",
            password="password",
        )

        assert conn._uri == "bolt://localhost:7687"
        assert conn._user == "neo4j"

    def test_close_without_connect(self):
        """Test closing without connecting doesn't raise."""
        from agentic_brain.pooling.neo4j_pool import DirectNeo4jConnection

        conn = DirectNeo4jConnection()
        conn.close()  # Should not raise


# ============================================================================
# HTTP Pool Tests
# ============================================================================


class TestHttpPoolConfig:
    """Tests for HttpPoolConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        from agentic_brain.pooling.http_pool import HttpPoolConfig

        config = HttpPoolConfig()

        assert config.pool_size == 100
        assert config.timeout == 30.0
        assert config.max_retries == 3
        assert config.circuit_failure_threshold == 5

    def test_env_override(self, monkeypatch):
        """Test environment variable override."""
        from agentic_brain.pooling.http_pool import HttpPoolConfig

        monkeypatch.setenv("HTTP_POOL_SIZE", "200")
        monkeypatch.setenv("CONNECTION_TIMEOUT", "60")

        config = HttpPoolConfig()

        assert config.pool_size == 200
        assert config.timeout == 60.0


class TestCircuitBreaker:
    """Tests for CircuitBreaker."""

    def test_initial_state(self):
        """Test circuit breaker initial state."""
        from agentic_brain.pooling.http_pool import CircuitBreaker, CircuitState

        circuit = CircuitBreaker(host="example.com")

        assert circuit.state == CircuitState.CLOSED
        assert circuit.failure_count == 0
        assert circuit.can_execute() is True

    def test_record_success_resets_failures(self):
        """Test that success resets failure count."""
        from agentic_brain.pooling.http_pool import CircuitBreaker

        circuit = CircuitBreaker(host="example.com")
        circuit.failure_count = 3

        circuit.record_success()

        assert circuit.failure_count == 0

    def test_circuit_opens_after_threshold(self):
        """Test circuit opens after failure threshold."""
        from agentic_brain.pooling.http_pool import CircuitBreaker, CircuitState

        circuit = CircuitBreaker(host="example.com", failure_threshold=3)

        circuit.record_failure()
        circuit.record_failure()
        assert circuit.state == CircuitState.CLOSED

        circuit.record_failure()
        assert circuit.state == CircuitState.OPEN
        assert circuit.can_execute() is False

    def test_circuit_half_open_after_timeout(self):
        """Test circuit goes half-open after recovery timeout."""
        from agentic_brain.pooling.http_pool import CircuitBreaker, CircuitState

        circuit = CircuitBreaker(
            host="example.com",
            failure_threshold=1,
            recovery_timeout=0.1,
        )

        circuit.record_failure()
        assert circuit.state == CircuitState.OPEN

        # Mock time to simulate recovery timeout passing
        import time as time_module
        from unittest.mock import patch

        future_time = time_module.time() + 0.2
        with patch.object(time_module, "time", return_value=future_time):
            assert circuit.can_execute() is True
            assert circuit.state == CircuitState.HALF_OPEN

    def test_circuit_closes_after_successes_in_half_open(self):
        """Test circuit closes after successful requests in half-open state."""
        from agentic_brain.pooling.http_pool import CircuitBreaker, CircuitState

        circuit = CircuitBreaker(host="example.com")
        circuit.state = CircuitState.HALF_OPEN

        circuit.record_success()
        circuit.record_success()
        assert circuit.state == CircuitState.HALF_OPEN

        circuit.record_success()
        assert circuit.state == CircuitState.CLOSED


class TestHttpPoolMetrics:
    """Tests for HttpPoolMetrics."""

    def test_initial_values(self):
        """Test initial metric values."""
        from agentic_brain.pooling.http_pool import HttpPoolMetrics

        metrics = HttpPoolMetrics()

        assert metrics.total_requests == 0
        assert metrics.successful_requests == 0
        assert metrics.failed_requests == 0

    def test_record_success(self):
        """Test recording successful request."""
        from agentic_brain.pooling.http_pool import HttpPoolMetrics

        metrics = HttpPoolMetrics()

        metrics.record_request(100.0, True)

        assert metrics.total_requests == 1
        assert metrics.successful_requests == 1
        assert metrics.average_response_time == 100.0

    def test_record_failure(self):
        """Test recording failed request."""
        from agentic_brain.pooling.http_pool import HttpPoolMetrics

        metrics = HttpPoolMetrics()

        metrics.record_request(0, False)

        assert metrics.total_requests == 1
        assert metrics.failed_requests == 1


class TestHttpResponse:
    """Tests for HttpResponse."""

    def test_response_ok(self):
        """Test response ok property."""
        from agentic_brain.pooling.http_pool import HttpResponse

        assert HttpResponse(200, {}, b"", 0).ok is True
        assert HttpResponse(201, {}, b"", 0).ok is True
        assert HttpResponse(299, {}, b"", 0).ok is True
        assert HttpResponse(300, {}, b"", 0).ok is False
        assert HttpResponse(404, {}, b"", 0).ok is False
        assert HttpResponse(500, {}, b"", 0).ok is False

    def test_response_text(self):
        """Test response text property."""
        from agentic_brain.pooling.http_pool import HttpResponse

        response = HttpResponse(200, {}, b"Hello World", 0)
        assert response.text == "Hello World"

    def test_response_json(self):
        """Test response json property."""
        from agentic_brain.pooling.http_pool import HttpResponse

        response = HttpResponse(200, {}, b'{"key": "value"}', 0)
        assert response.json == {"key": "value"}


class TestHttpPool:
    """Tests for HttpPool."""

    def test_pool_initialization(self):
        """Test pool initialization."""
        from agentic_brain.pooling.http_pool import HttpPool, HttpPoolConfig

        config = HttpPoolConfig(pool_size=50)
        pool = HttpPool(config)

        assert pool.config.pool_size == 50
        assert not pool.is_started

    @pytest.mark.asyncio
    async def test_startup_and_shutdown(self):
        """Test pool startup and shutdown."""
        from agentic_brain.pooling.http_pool import HttpPool

        pool = HttpPool()

        await pool.startup()
        assert pool.is_started

        await pool.shutdown()
        assert not pool.is_started

    @pytest.mark.asyncio
    async def test_request_without_startup(self):
        """Test request without startup raises error."""
        from agentic_brain.pooling.http_pool import HttpPool

        pool = HttpPool()

        with pytest.raises(RuntimeError, match="not started"):
            await pool.get("https://example.com")

    @pytest.mark.asyncio
    async def test_health_check_not_started(self):
        """Test health check when pool not started."""
        from agentic_brain.pooling.http_pool import HttpPool

        pool = HttpPool()
        health = await pool.health_check()

        assert health["healthy"] is False
        assert health["started"] is False


class TestDirectHttpClient:
    """Tests for DirectHttpClient fallback."""

    def test_initialization(self):
        """Test direct client initialization."""
        from agentic_brain.pooling.http_pool import DirectHttpClient

        client = DirectHttpClient(timeout=60.0)
        assert client._timeout == 60.0


# ============================================================================
# Pool Manager Tests
# ============================================================================


class TestPoolManagerConfig:
    """Tests for PoolManagerConfig."""

    def test_default_values(self):
        """Test default configuration values."""
        from agentic_brain.pooling.manager import PoolManagerConfig

        config = PoolManagerConfig()

        assert config.enable_neo4j is True
        assert config.enable_http is True

    def test_disable_via_env(self, monkeypatch):
        """Test disabling pools via environment."""
        from agentic_brain.pooling.manager import PoolManagerConfig

        monkeypatch.setenv("POOL_ENABLE_NEO4J", "false")
        monkeypatch.setenv("POOL_ENABLE_HTTP", "false")

        config = PoolManagerConfig()

        assert config.enable_neo4j is False
        assert config.enable_http is False


class TestPoolManager:
    """Tests for PoolManager."""

    def test_singleton_pattern(self):
        """Test singleton pattern."""
        from agentic_brain.pooling.manager import PoolManager

        PoolManager.reset_instance()

        manager1 = PoolManager.get_instance()
        manager2 = PoolManager.get_instance()

        assert manager1 is manager2

        PoolManager.reset_instance()

    def test_reset_instance(self):
        """Test reset instance."""
        from agentic_brain.pooling.manager import PoolManager

        manager1 = PoolManager.get_instance()
        PoolManager.reset_instance()
        manager2 = PoolManager.get_instance()

        assert manager1 is not manager2

        PoolManager.reset_instance()

    @pytest.mark.asyncio
    async def test_startup_and_shutdown(self):
        """Test manager startup and shutdown."""
        from agentic_brain.pooling.manager import PoolManager, PoolManagerConfig

        config = PoolManagerConfig(enable_neo4j=False)  # Disable Neo4j for test
        manager = PoolManager(config)

        await manager.startup()
        assert manager.is_started

        await manager.shutdown()
        assert not manager.is_started

    @pytest.mark.asyncio
    async def test_neo4j_access_before_startup(self):
        """Test accessing Neo4j before startup raises error."""
        from agentic_brain.pooling.manager import PoolManager

        manager = PoolManager()

        with pytest.raises(RuntimeError, match="not started"):
            _ = manager.neo4j

    @pytest.mark.asyncio
    async def test_http_access_before_startup(self):
        """Test accessing HTTP before startup raises error."""
        from agentic_brain.pooling.manager import PoolManager

        manager = PoolManager()

        with pytest.raises(RuntimeError, match="not started"):
            _ = manager.http

    @pytest.mark.asyncio
    async def test_neo4j_disabled(self):
        """Test accessing disabled Neo4j raises error."""
        from agentic_brain.pooling.manager import PoolManager, PoolManagerConfig

        config = PoolManagerConfig(enable_neo4j=False)
        manager = PoolManager(config)

        await manager.startup()

        with pytest.raises(RuntimeError, match="not enabled"):
            _ = manager.neo4j

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_health_check_not_started(self):
        """Test health check when not started."""
        from agentic_brain.pooling.manager import PoolManager

        manager = PoolManager()
        health = await manager.health_check()

        assert health["healthy"] is False
        assert health["started"] is False

    @pytest.mark.asyncio
    async def test_health_check_started(self):
        """Test health check when started."""
        from agentic_brain.pooling.manager import PoolManager, PoolManagerConfig

        config = PoolManagerConfig(enable_neo4j=False)  # Disable Neo4j for test
        manager = PoolManager(config)

        await manager.startup()
        health = await manager.health_check()

        assert health["started"] is True
        assert "http" in health["pools"]

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_get_metrics(self):
        """Test getting pool metrics."""
        from agentic_brain.pooling.manager import PoolManager, PoolManagerConfig

        config = PoolManagerConfig(enable_neo4j=False)
        manager = PoolManager(config)

        await manager.startup()
        metrics = manager.get_metrics()

        assert "http" in metrics
        assert "total_requests" in metrics["http"]

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_startup_idempotent(self):
        """Test that startup can be called multiple times."""
        from agentic_brain.pooling.manager import PoolManager, PoolManagerConfig

        config = PoolManagerConfig(enable_neo4j=False, enable_http=False)
        manager = PoolManager(config)

        await manager.startup()
        await manager.startup()  # Should not raise

        assert manager.is_started

        await manager.shutdown()

    @pytest.mark.asyncio
    async def test_shutdown_idempotent(self):
        """Test that shutdown can be called multiple times."""
        from agentic_brain.pooling.manager import PoolManager

        manager = PoolManager()

        await manager.shutdown()
        await manager.shutdown()  # Should not raise


class TestConvenienceFunctions:
    """Tests for convenience functions."""

    @pytest.mark.asyncio
    async def test_get_pool_manager(self):
        """Test get_pool_manager starts manager."""
        from agentic_brain.pooling.manager import (
            PoolManager,
            get_pool_manager,
            shutdown_pools,
        )

        PoolManager.reset_instance()

        # Get and start manager
        manager = await get_pool_manager()
        assert manager.is_started

        # Cleanup
        await shutdown_pools()

    @pytest.mark.asyncio
    async def test_shutdown_pools(self):
        """Test shutdown_pools function."""
        from agentic_brain.pooling.manager import (
            PoolManager,
            shutdown_pools,
        )

        PoolManager.get_instance()

        # Should not raise even if not started
        await shutdown_pools()


# ============================================================================
# Integration Tests
# ============================================================================


class TestPoolingIntegration:
    """Integration tests for pooling."""

    @pytest.mark.asyncio
    async def test_full_lifecycle(self):
        """Test full pool manager lifecycle."""
        from agentic_brain.pooling import PoolManager
        from agentic_brain.pooling.manager import PoolManagerConfig

        config = PoolManagerConfig(enable_neo4j=False)
        manager = PoolManager(config)

        # Start
        await manager.startup()
        assert manager.is_started

        # Health check
        health = await manager.health_check()
        assert health["healthy"] is True

        # Get metrics
        metrics = manager.get_metrics()
        assert isinstance(metrics, dict)

        # Shutdown
        await manager.shutdown()
        assert not manager.is_started

    @pytest.mark.asyncio
    async def test_pool_module_imports(self):
        """Test that all expected classes are importable."""
        from agentic_brain.pooling import (
            HttpPool,
            HttpPoolConfig,
            Neo4jPool,
            Neo4jPoolConfig,
            PoolManager,
        )

        assert Neo4jPool is not None
        assert Neo4jPoolConfig is not None
        assert HttpPool is not None
        assert HttpPoolConfig is not None
        assert PoolManager is not None
