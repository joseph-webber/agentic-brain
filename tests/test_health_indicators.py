# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""Tests for pluggable health indicators."""

import asyncio
from datetime import datetime, timezone

import pytest

from agentic_brain.health import (
    DiskSpaceHealthIndicator,
    Health,
    HealthIndicator,
    HealthIndicatorRegistry,
    HealthStatus,
    PingHealthIndicator,
)


class TestHealthStatus:
    """Tests for HealthStatus enum."""

    def test_worst_single(self):
        """Test worst with single status."""
        assert HealthStatus.worst(HealthStatus.UP) == HealthStatus.UP
        assert HealthStatus.worst(HealthStatus.DOWN) == HealthStatus.DOWN

    def test_worst_multiple(self):
        """Test worst prioritizes DOWN."""
        result = HealthStatus.worst(
            HealthStatus.UP, HealthStatus.DOWN, HealthStatus.UNKNOWN
        )
        assert result == HealthStatus.DOWN

    def test_worst_degraded(self):
        """Test OUT_OF_SERVICE is worse than UNKNOWN."""
        result = HealthStatus.worst(HealthStatus.UNKNOWN, HealthStatus.OUT_OF_SERVICE)
        assert result == HealthStatus.OUT_OF_SERVICE

    def test_worst_empty(self):
        """Test worst with no statuses."""
        assert HealthStatus.worst() == HealthStatus.UNKNOWN


class TestHealth:
    """Tests for Health result class."""

    def test_up(self):
        """Test Health.up factory."""
        health = Health.up(foo="bar")
        assert health.status == HealthStatus.UP
        assert health.details["foo"] == "bar"

    def test_down(self):
        """Test Health.down factory."""
        health = Health.down(error="Connection failed")
        assert health.status == HealthStatus.DOWN
        assert health.error == "Connection failed"

    def test_down_with_details(self):
        """Test Health.down with additional details."""
        health = Health.down(error="Timeout", timeout_ms=5000)
        assert health.details["timeout_ms"] == 5000

    def test_unknown(self):
        """Test Health.unknown factory."""
        health = Health.unknown(reason="Not configured")
        assert health.status == HealthStatus.UNKNOWN

    def test_with_detail(self):
        """Test adding details fluently."""
        health = Health.up().with_detail("version", "1.0.0")
        assert health.details["version"] == "1.0.0"

    def test_with_exception(self):
        """Test adding exception info."""
        try:
            raise ValueError("Test error")
        except Exception as e:
            health = Health.down().with_exception(e)
            assert "ValueError" in health.error
            assert "Test error" in health.error


class TestPingHealthIndicator:
    """Tests for ping health indicator."""

    @pytest.mark.asyncio
    async def test_always_up(self):
        """Test ping always returns UP."""
        indicator = PingHealthIndicator()
        health = await indicator.health()
        assert health.status == HealthStatus.UP

    def test_name(self):
        """Test indicator name."""
        indicator = PingHealthIndicator()
        assert indicator.name == "ping"


class TestDiskSpaceHealthIndicator:
    """Tests for disk space health indicator."""

    @pytest.mark.asyncio
    async def test_disk_check(self):
        """Test disk space check runs."""
        indicator = DiskSpaceHealthIndicator(path="/")
        health = await indicator.health()
        # Should return UP unless disk is actually full
        assert health.status in [HealthStatus.UP, HealthStatus.DOWN]
        assert "free_gb" in health.details
        assert "total_gb" in health.details

    @pytest.mark.asyncio
    async def test_threshold_check(self):
        """Test with very high threshold (should fail)."""
        # Set threshold to 1 PB (should always fail)
        indicator = DiskSpaceHealthIndicator(
            path="/", threshold_bytes=1024**5  # 1 petabyte
        )
        health = await indicator.health()
        assert health.status == HealthStatus.DOWN


class CustomHealthIndicator(HealthIndicator):
    """Custom health indicator for testing."""

    def __init__(self, status: HealthStatus = HealthStatus.UP, delay: float = 0):
        self._status = status
        self._delay = delay

    async def health(self) -> Health:
        if self._delay > 0:
            await asyncio.sleep(self._delay)
        if self._status == HealthStatus.UP:
            return Health.up(custom="test")
        return Health.down(error="Custom failure")


class TestHealthIndicatorRegistry:
    """Tests for health indicator registry."""

    @pytest.mark.asyncio
    async def test_register_and_check(self):
        """Test registering and checking indicator."""
        registry = HealthIndicatorRegistry()
        registry.register(CustomHealthIndicator(), "custom")

        health = await registry.check("custom")
        assert health.status == HealthStatus.UP
        assert health.details["custom"] == "test"

    @pytest.mark.asyncio
    async def test_check_unknown(self):
        """Test checking non-existent indicator."""
        registry = HealthIndicatorRegistry()
        health = await registry.check("nonexistent")
        assert health.status == HealthStatus.UNKNOWN
        assert "Unknown indicator" in health.details.get("error", "")

    @pytest.mark.asyncio
    async def test_check_all(self):
        """Test checking all indicators."""
        registry = HealthIndicatorRegistry()
        registry.register(CustomHealthIndicator(HealthStatus.UP), "service1")
        registry.register(CustomHealthIndicator(HealthStatus.UP), "service2")

        health = await registry.check_all()
        assert health.status == HealthStatus.UP
        assert "service1" in health.components
        assert "service2" in health.components

    @pytest.mark.asyncio
    async def test_check_all_with_failure(self):
        """Test aggregation with one failing indicator."""
        registry = HealthIndicatorRegistry()
        registry.register(CustomHealthIndicator(HealthStatus.UP), "healthy")
        registry.register(CustomHealthIndicator(HealthStatus.DOWN), "unhealthy")

        health = await registry.check_all()
        assert health.status == HealthStatus.DOWN

    def test_list_indicators(self):
        """Test listing registered indicators."""
        registry = HealthIndicatorRegistry()
        registry.register(PingHealthIndicator(), "ping")
        registry.register(CustomHealthIndicator(), "custom")

        names = registry.list_indicators()
        assert "ping" in names
        assert "custom" in names

    def test_unregister(self):
        """Test unregistering indicator."""
        registry = HealthIndicatorRegistry()
        registry.register(CustomHealthIndicator(), "custom")
        assert "custom" in registry.list_indicators()

        result = registry.unregister("custom")
        assert result is True
        assert "custom" not in registry.list_indicators()

    @pytest.mark.asyncio
    async def test_liveness(self):
        """Test liveness probe."""
        registry = HealthIndicatorRegistry()
        health = await registry.liveness()
        assert health.status == HealthStatus.UP
        assert "timestamp" in health.details

    @pytest.mark.asyncio
    async def test_readiness(self):
        """Test readiness probe."""
        registry = HealthIndicatorRegistry()
        registry.register(CustomHealthIndicator(), "dep")
        health = await registry.readiness()
        assert health.status == HealthStatus.UP

    @pytest.mark.asyncio
    async def test_timeout_handling(self):
        """Test timeout for slow health checks."""
        registry = HealthIndicatorRegistry()
        registry._timeout_seconds = 0.1  # Very short timeout

        # Indicator that takes too long
        slow_indicator = CustomHealthIndicator(delay=1.0)
        registry.register(slow_indicator, "slow")

        health = await registry.check("slow")
        assert health.status == HealthStatus.DOWN
        assert "timeout" in health.error.lower()
