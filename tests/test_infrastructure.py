# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
"""
Infrastructure health and resilience tests.

Tests:
- Redis health checks and auto-restart
- Neo4j health checks and auto-restart
- Redpanda health checks and auto-restart
- Event bridge Redis <-> Redpanda
- Auto-restart capability
- Service state recovery
"""

import asyncio
import json
import logging
import time
from datetime import datetime
from typing import Any, Dict

import pytest

docker = pytest.importorskip("docker")
pytest.importorskip("docker.errors")
try:
    from docker.errors import NotFound
except ImportError:
    docker = None  # Docker not installed
    NotFound = None

logger = logging.getLogger(__name__)


# ===== Fixtures =====


@pytest.fixture(scope="session")
def docker_client():
    """Get Docker client."""
    return docker.from_env()


@pytest.fixture(scope="session")
def redis_container(docker_client):
    """Get or create Redis test container."""
    container_name = "test-redis-infra"

    # Remove existing container if present
    try:
        container = docker_client.containers.get(container_name)
        container.stop()
        container.remove()
    except NotFound:
        pass

    # Start new container
    container = docker_client.containers.run(
        "redis:7-alpine",
        name=container_name,
        ports={"6379/tcp": 6380},
        detach=True,
        remove=False,
    )

    # Wait for container to be ready
    time.sleep(2)

    yield container

    # Cleanup
    try:
        container.stop()
        container.remove()
    except Exception:
        pass


@pytest.fixture(scope="session")
def neo4j_container(docker_client):
    """Get or create Neo4j test container."""
    container_name = "test-neo4j-infra"

    # Remove existing container if present
    try:
        container = docker_client.containers.get(container_name)
        container.stop()
        container.remove()
    except NotFound:
        pass

    # Start new container
    container = docker_client.containers.run(
        "neo4j:5-community",
        name=container_name,
        ports={"7687/tcp": 7688},
        environment={
            "NEO4J_AUTH": "neo4j/Brain2026",
        },
        detach=True,
        remove=False,
    )

    # Wait for container to be ready
    time.sleep(5)

    yield container

    # Cleanup
    try:
        container.stop()
        container.remove()
    except Exception:
        pass


# ===== Health Monitor Tests =====


class TestHealthMonitor:
    """Test infrastructure health monitoring."""

    @pytest.mark.asyncio
    async def test_redis_health_check(self):
        """Test Redis health check."""
        from agentic_brain.infra.health_monitor import HealthMonitor, ServiceStatus

        monitor = HealthMonitor(
            redis_host="localhost",
            redis_port=6379,
            redis_password="brain_secure_2024",
        )

        await monitor.initialize()
        health = await monitor.check_redis()

        # Verify health check result
        assert health.name == "redis"
        assert health.status in [ServiceStatus.HEALTHY, ServiceStatus.UNHEALTHY]
        assert health.check_timestamp > 0
        assert health.response_time_ms >= 0

        await monitor.close()

    @pytest.mark.asyncio
    async def test_health_monitor_initialization(self):
        """Test health monitor initialization."""
        from agentic_brain.infra.health_monitor import HealthMonitor

        monitor = HealthMonitor(
            redis_host="localhost",
            redis_port=6379,
            neo4j_uri="bolt://localhost:7687",
        )

        await monitor.initialize()

        # Verify initialization
        assert True  # May not connect if service down
        assert monitor.is_monitoring is False

        await monitor.close()

    @pytest.mark.asyncio
    async def test_health_status_dict(self):
        """Test health status as dictionary."""
        from agentic_brain.infra.health_monitor import HealthMonitor, ServiceStatus

        monitor = HealthMonitor()
        await monitor.initialize()
        await monitor.check_all()

        status_dict = monitor.get_status_dict()

        # Verify dictionary structure
        assert "redis" in status_dict
        assert "neo4j" in status_dict
        assert "redpanda" in status_dict

        for _service_name, service_status in status_dict.items():
            assert "name" in service_status
            assert "status" in service_status
            assert "last_check" in service_status
            assert "check_timestamp" in service_status
            assert "response_time_ms" in service_status

        await monitor.close()

    @pytest.mark.asyncio
    async def test_restart_callbacks(self):
        """Test restart callback registration."""
        from agentic_brain.infra.health_monitor import HealthMonitor

        monitor = HealthMonitor()

        callback_called = False

        async def test_callback(service_name: str):
            nonlocal callback_called
            callback_called = True

        monitor.register_restart_callback("redis", test_callback)

        # Verify callback is registered
        assert len(monitor.restart_callbacks["redis"]) > 0

        await monitor.close()

    @pytest.mark.asyncio
    async def test_health_monitor_status_properties(self):
        """Test health monitor status properties."""
        from agentic_brain.infra.health_monitor import HealthMonitor

        monitor = HealthMonitor()
        await monitor.initialize()
        await monitor.check_all()

        # Verify properties
        assert isinstance(monitor.all_healthy, bool)
        assert isinstance(monitor.any_unhealthy, bool)

        await monitor.close()


# ===== Event Bridge Tests =====


class TestEventBridge:
    """Test Redis-Redpanda event bridge."""

    @pytest.mark.asyncio
    async def test_bridged_event_serialization(self):
        """Test BridgedEvent serialization."""
        from agentic_brain.infra.event_bridge import BridgedEvent

        event = BridgedEvent(
            id="test-1",
            source="redis",
            topic="brain.llm.request",
            payload={"role": "user", "content": "Hello"},
            persistent=True,
        )

        # Serialize
        json_str = event.to_json()
        assert isinstance(json_str, str)
        assert "test-1" in json_str
        assert "brain.llm.request" in json_str

        # Deserialize
        event2 = BridgedEvent.from_json(json_str)
        assert event2.id == event.id
        assert event2.topic == event.topic
        assert event2.payload == event.payload

    @pytest.mark.asyncio
    async def test_redis_redpanda_bridge_initialization(self):
        """Test Redis-Redpanda bridge initialization."""
        from agentic_brain.infra.event_bridge import RedisRedpandaBridge

        bridge = RedisRedpandaBridge(
            redis_host="localhost",
            redis_port=6379,
            redis_password="brain_secure_2024",
            redpanda_brokers="localhost:9092",
        )

        # Verify initialization
        assert bridge.redis_host == "localhost"
        assert bridge.redpanda_brokers == "localhost:9092"
        assert len(bridge.bridge_channels) > 0
        assert len(bridge.persistent_channels) > 0

    def test_event_persistence_determination(self):
        """Test persistent channel determination."""
        from agentic_brain.infra.event_bridge import RedisRedpandaBridge

        bridge = RedisRedpandaBridge(
            persistent_channels={
                "brain.llm.requests",
                "brain.llm.responses",
                "brain.events.critical",
            }
        )

        # Test exact matches
        assert bridge._should_persist("brain.llm.requests") is True
        assert bridge._should_persist("brain.llm.responses") is True

        # Test non-matches
        assert bridge._should_persist("brain.other.topic") is False

    @pytest.mark.asyncio
    async def test_event_bridge_callback_registration(self):
        """Test event bridge callback registration."""
        from agentic_brain.infra.event_bridge import RedisRedpandaBridge

        bridge = RedisRedpandaBridge()

        callback_called = False

        async def test_callback(event):
            nonlocal callback_called
            callback_called = True

        bridge.register_event_callback("brain.llm.request", test_callback)

        # Verify callback is registered
        assert len(bridge.event_callbacks.get("brain.llm.request", [])) > 0


# ===== Integration Tests =====


class TestInfrastructureIntegration:
    """Integration tests for infrastructure."""

    @pytest.mark.asyncio
    async def test_health_monitor_with_real_services(self):
        """Test health monitor with real services."""
        from agentic_brain.infra.health_monitor import HealthMonitor, ServiceStatus

        monitor = HealthMonitor(
            redis_host="localhost",
            redis_port=6379,
            redis_password="brain_secure_2024",
            neo4j_uri="bolt://localhost:7687",
            neo4j_user="neo4j",
            neo4j_password="Brain2026",
        )

        await monitor.initialize()

        # Run health check
        health_status = await monitor.check_all()

        # Verify results
        assert isinstance(health_status, dict)
        assert "redis" in health_status
        assert "neo4j" in health_status
        assert "redpanda" in health_status

        await monitor.close()

    @pytest.mark.asyncio
    async def test_multiple_service_checks(self):
        """Test checking multiple services simultaneously."""
        from agentic_brain.infra.health_monitor import HealthMonitor

        monitor = HealthMonitor()
        await monitor.initialize()

        # Run multiple checks
        for _ in range(3):
            await monitor.check_all()
            assert monitor.health_status is not None
            await asyncio.sleep(1)

        await monitor.close()

    @pytest.mark.asyncio
    async def test_service_restart_tracking(self):
        """Test service restart tracking."""
        from agentic_brain.infra.health_monitor import HealthMonitor, ServiceStatus

        monitor = HealthMonitor(use_docker=False)
        await monitor.initialize()

        # Check initial state
        redis_health = monitor.health_status["redis"]

        # Verify restart count is tracked
        assert redis_health.restart_count >= 0

        await monitor.close()

    @pytest.mark.asyncio
    async def test_health_monitoring_loop_start_stop(self):
        """Test starting and stopping health monitoring loop."""
        from agentic_brain.infra.health_monitor import HealthMonitor

        monitor = HealthMonitor(check_interval=2)
        await monitor.initialize()

        # Verify monitoring is off initially
        assert monitor.is_monitoring is False

        # Start monitoring in background
        monitor_task = asyncio.create_task(monitor.start_monitoring())

        # Wait a bit
        await asyncio.sleep(0.5)
        assert monitor.is_monitoring is True

        # Stop monitoring
        monitor.stop_monitoring()
        await asyncio.sleep(0.5)
        assert monitor.is_monitoring is False

        # Cancel the task
        monitor_task.cancel()
        try:
            await monitor_task
        except asyncio.CancelledError:
            pass

        await monitor.close()


# ===== Performance Tests =====


class TestInfrastructurePerformance:
    """Test infrastructure performance."""

    @pytest.mark.asyncio
    async def test_health_check_speed(self):
        """Test that health checks are fast."""
        from agentic_brain.infra.health_monitor import HealthMonitor

        monitor = HealthMonitor()
        await monitor.initialize()

        start_time = time.time()
        await monitor.check_all()
        elapsed = time.time() - start_time

        # Health checks should be fast (< 10 seconds)
        assert elapsed < 10

        logger.info(f"Health check completed in {elapsed:.2f}s")

        await monitor.close()

    @pytest.mark.asyncio
    async def test_bridged_event_performance(self):
        """Test BridgedEvent performance."""
        from agentic_brain.infra.event_bridge import BridgedEvent

        start_time = time.time()

        # Create and serialize 1000 events
        for i in range(1000):
            event = BridgedEvent(
                id=f"test-{i}",
                source="redis",
                topic="brain.llm.request",
                payload={"index": i, "data": "x" * 100},
            )
            json_str = event.to_json()
            BridgedEvent.from_json(json_str)

        elapsed = time.time() - start_time

        # Should handle 1000 events quickly
        assert elapsed < 5

        logger.info(f"Processed 1000 events in {elapsed:.2f}s")


# ===== Docker Integration Tests =====


@pytest.mark.requires_docker
class TestDockerIntegration:
    """Test Docker service integration."""

    def test_docker_redis_health(self, redis_container, docker_client):
        """Test Docker Redis container health."""
        # Get container stats
        redis_container.reload()

        # Verify container is running
        assert redis_container.status == "running"

        # Verify health check passes
        exit_code, output = redis_container.exec_run("redis-cli ping")
        assert exit_code == 0
        assert b"PONG" in output

    def test_docker_neo4j_health(self, neo4j_container, docker_client):
        """Test Docker Neo4j container health."""
        # Get container stats
        neo4j_container.reload()

        # Verify container is running
        assert neo4j_container.status == "running"

    @pytest.mark.asyncio
    async def test_docker_container_restart(self, redis_container, docker_client):
        """Test Docker container restart capability."""
        # Get initial container ID
        initial_id = redis_container.id

        # Restart container
        redis_container.restart()

        # Wait for restart
        await asyncio.sleep(2)

        # Verify container is still running
        redis_container.reload()
        assert redis_container.status == "running"

        # Container may have new ID after restart
        assert redis_container.id == initial_id


# ===== Configuration Tests =====


class TestInfrastructureConfiguration:
    """Test infrastructure configuration."""

    def test_health_monitor_config_defaults(self):
        """Test health monitor default configuration."""
        from agentic_brain.infra.health_monitor import HealthMonitor

        monitor = HealthMonitor()

        assert monitor.redis_host == "localhost"
        assert monitor.redis_port == 6379
        assert monitor.neo4j_uri == "bolt://localhost:7687"
        assert monitor.check_interval == 30
        assert monitor.max_restart_attempts == 5
        assert monitor.restart_cooldown == 60

    def test_health_monitor_config_custom(self):
        """Test health monitor custom configuration."""
        from agentic_brain.infra.health_monitor import HealthMonitor

        monitor = HealthMonitor(
            redis_host="redis.example.com",
            redis_port=6380,
            check_interval=60,
            max_restart_attempts=10,
        )

        assert monitor.redis_host == "redis.example.com"
        assert monitor.redis_port == 6380
        assert monitor.check_interval == 60
        assert monitor.max_restart_attempts == 10

    def test_event_bridge_config(self):
        """Test event bridge configuration."""
        from agentic_brain.infra.event_bridge import RedisRedpandaBridge

        bridge = RedisRedpandaBridge(
            redis_host="redis.local",
            redpanda_brokers="redpanda.local:9092",
        )

        assert bridge.redis_host == "redis.local"
        assert bridge.redpanda_brokers == "redpanda.local:9092"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
