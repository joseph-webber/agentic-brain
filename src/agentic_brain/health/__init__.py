# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber

"""
Pluggable Health Indicators (JHipster-aligned).

Provides a Spring Boot Actuator-style health check framework with:
- Component-level health checks
- Aggregated system health
- Custom health indicator registration
- Async health checks with timeouts
- Health endpoint integration

JHipster equivalent: actuator/health/*
Spring Boot equivalent: org.springframework.boot.actuate.health.*
"""

import asyncio
import logging
from abc import ABC, abstractmethod
from datetime import UTC, datetime, timezone
from enum import Enum
from typing import Any, Optional

from pydantic import BaseModel, Field

logger = logging.getLogger(__name__)


class HealthStatus(str, Enum):
    """
    Health status values matching Spring Boot Actuator.

    Status hierarchy (worst to best):
    DOWN > OUT_OF_SERVICE > UNKNOWN > UP
    """

    UP = "UP"
    DOWN = "DOWN"
    OUT_OF_SERVICE = "OUT_OF_SERVICE"
    UNKNOWN = "UNKNOWN"

    @classmethod
    def worst(cls, *statuses: "HealthStatus") -> "HealthStatus":
        """Return the worst status from a collection."""
        order = [cls.DOWN, cls.OUT_OF_SERVICE, cls.UNKNOWN, cls.UP]
        for status in order:
            if status in statuses:
                return status
        return cls.UNKNOWN


class Health(BaseModel):
    """
    Health indicator result.

    Matches Spring Boot Health class structure.
    """

    status: HealthStatus = HealthStatus.UNKNOWN
    details: dict[str, Any] = Field(default_factory=dict)
    components: dict[str, "Health"] = Field(default_factory=dict)
    error: Optional[str] = None

    @classmethod
    def up(cls, **details: Any) -> "Health":
        """Create an UP health result."""
        return cls(status=HealthStatus.UP, details=details)

    @classmethod
    def down(cls, error: Optional[str] = None, **details: Any) -> "Health":
        """Create a DOWN health result."""
        return cls(status=HealthStatus.DOWN, error=error, details=details)

    @classmethod
    def out_of_service(cls, **details: Any) -> "Health":
        """Create an OUT_OF_SERVICE health result."""
        return cls(status=HealthStatus.OUT_OF_SERVICE, details=details)

    @classmethod
    def unknown(cls, **details: Any) -> "Health":
        """Create an UNKNOWN health result."""
        return cls(status=HealthStatus.UNKNOWN, details=details)

    def with_detail(self, key: str, value: Any) -> "Health":
        """Add a detail to the health result."""
        self.details[key] = value
        return self

    def with_exception(self, error: Exception) -> "Health":
        """Add exception info to the health result."""
        self.error = f"{type(error).__name__}: {str(error)}"
        return self


class HealthIndicator(ABC):
    """
    Abstract health indicator interface.

    Implement this to create custom health checks for your components.

    Example:
        class Neo4jHealthIndicator(HealthIndicator):
            async def health(self) -> Health:
                try:
                    await driver.verify_connectivity()
                    return Health.up(database="neo4j")
                except Exception as e:
                    return Health.down().with_exception(e)
    """

    @abstractmethod
    async def health(self) -> Health:
        """Check health and return status."""
        pass

    @property
    def name(self) -> str:
        """Get indicator name (defaults to class name without 'HealthIndicator')."""
        class_name = self.__class__.__name__
        if class_name.endswith("HealthIndicator"):
            return class_name[:-15].lower()
        return class_name.lower()


class PingHealthIndicator(HealthIndicator):
    """Simple health indicator that always returns UP."""

    async def health(self) -> Health:
        return Health.up()


class DiskSpaceHealthIndicator(HealthIndicator):
    """
    Check available disk space.

    Reports DOWN if free space falls below threshold.
    """

    def __init__(
        self,
        path: str = "/",
        threshold_bytes: int = 10 * 1024 * 1024 * 1024,  # 10 GB
    ) -> None:
        self.path = path
        self.threshold_bytes = threshold_bytes

    async def health(self) -> Health:
        try:
            import shutil

            usage = shutil.disk_usage(self.path)
            free_gb = usage.free / (1024**3)
            total_gb = usage.total / (1024**3)

            details = {
                "path": self.path,
                "free_gb": round(free_gb, 2),
                "total_gb": round(total_gb, 2),
                "threshold_gb": round(self.threshold_bytes / (1024**3), 2),
            }

            if usage.free < self.threshold_bytes:
                return Health.down(**details)
            return Health.up(**details)

        except Exception as e:
            return Health.down().with_exception(e)


class MemoryHealthIndicator(HealthIndicator):
    """
    Check memory usage.

    Reports DOWN if memory usage exceeds threshold.
    """

    def __init__(self, threshold_percent: float = 90.0) -> None:
        self.threshold_percent = threshold_percent

    async def health(self) -> Health:
        try:
            import psutil

            memory = psutil.virtual_memory()
            details = {
                "total_gb": round(memory.total / (1024**3), 2),
                "available_gb": round(memory.available / (1024**3), 2),
                "used_percent": memory.percent,
                "threshold_percent": self.threshold_percent,
            }

            if memory.percent > self.threshold_percent:
                return Health.down(**details)
            return Health.up(**details)

        except ImportError:
            return Health.unknown(error="psutil not installed")
        except Exception as e:
            return Health.down().with_exception(e)


class Neo4jHealthIndicator(HealthIndicator):
    """
    Check Neo4j database connectivity.

    Verifies connection and runs a simple query.
    """

    def __init__(self, driver: Any = None, uri: Optional[str] = None) -> None:
        self._driver = driver
        self._uri = uri

    async def health(self) -> Health:
        try:
            driver = self._driver
            if driver is None:
                try:
                    from agentic_brain.memory.neo4j_pool import get_neo4j_pool

                    pool = get_neo4j_pool()
                    driver = pool._driver if pool else None
                except Exception:
                    pass

            if driver is None:
                return Health.down(error="No Neo4j driver configured")

            # Verify connectivity
            await asyncio.wait_for(
                asyncio.to_thread(driver.verify_connectivity),
                timeout=5.0,
            )

            # Get server info
            with driver.session() as session:
                result = session.run(
                    "CALL dbms.components() YIELD name, versions, edition"
                )
                record = result.single()
                if record:
                    return Health.up(
                        database="neo4j",
                        version=(
                            record["versions"][0] if record["versions"] else "unknown"
                        ),
                        edition=record["edition"],
                    )

            return Health.up(database="neo4j")

        except TimeoutError:
            return Health.down(error="Connection timeout")
        except Exception as e:
            return Health.down().with_exception(e)


class RedisHealthIndicator(HealthIndicator):
    """
    Check Redis connectivity.

    Runs PING command to verify connection.
    """

    def __init__(self, client: Any = None, url: Optional[str] = None) -> None:
        self._client = client
        self._url = url

    async def health(self) -> Health:
        try:
            client = self._client
            if client is None:
                try:
                    import redis.asyncio as redis

                    url = self._url or "redis://localhost:6379"
                    client = redis.from_url(url)
                except ImportError:
                    return Health.unknown(error="redis package not installed")

            # Ping Redis
            result = await asyncio.wait_for(client.ping(), timeout=3.0)
            if result:
                info = await client.info(section="server")
                return Health.up(
                    version=info.get("redis_version", "unknown"),
                    mode=info.get("redis_mode", "unknown"),
                )

            return Health.down(error="PING failed")

        except TimeoutError:
            return Health.down(error="Connection timeout")
        except Exception as e:
            return Health.down().with_exception(e)


class LLMHealthIndicator(HealthIndicator):
    """
    Check LLM provider connectivity.

    Verifies the configured LLM provider is reachable.
    """

    def __init__(self, router: Any = None) -> None:
        self._router = router

    async def health(self) -> Health:
        try:
            router = self._router
            if router is None:
                try:
                    from agentic_brain.router import LLMRouter

                    router = LLMRouter()
                except Exception:
                    return Health.unknown(error="LLMRouter not available")

            # Check available providers
            providers = []
            details: dict[str, Any] = {}

            # Check Ollama
            try:
                from agentic_brain.router.provider_checker import check_ollama

                ollama_ok = await check_ollama()
                if ollama_ok:
                    providers.append("ollama")
                    details["ollama"] = "available"
            except Exception:
                pass

            # Check OpenAI
            import os

            if os.getenv("OPENAI_API_KEY"):
                providers.append("openai")
                details["openai"] = "configured"

            # Check Anthropic
            if os.getenv("ANTHROPIC_API_KEY"):
                providers.append("anthropic")
                details["anthropic"] = "configured"

            # Check Groq
            if os.getenv("GROQ_API_KEY"):
                providers.append("groq")
                details["groq"] = "configured"

            if providers:
                details["providers"] = providers
                details["primary"] = providers[0]
                return Health.up(**details)

            return Health.down(error="No LLM providers available", **details)

        except Exception as e:
            return Health.down().with_exception(e)


class HttpHealthIndicator(HealthIndicator):
    """
    Check HTTP endpoint connectivity.

    Useful for checking external service dependencies.
    """

    def __init__(
        self,
        url: str,
        name: str = "http",
        timeout_seconds: float = 5.0,
        expected_status: int = 200,
    ) -> None:
        self._url = url
        self._name = name
        self._timeout = timeout_seconds
        self._expected_status = expected_status

    @property
    def name(self) -> str:
        return self._name

    async def health(self) -> Health:
        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    self._url,
                    timeout=aiohttp.ClientTimeout(total=self._timeout),
                ) as response:
                    if response.status == self._expected_status:
                        return Health.up(
                            url=self._url,
                            status=response.status,
                        )
                    return Health.down(
                        url=self._url,
                        status=response.status,
                        expected=self._expected_status,
                    )

        except TimeoutError:
            return Health.down(error="Connection timeout", url=self._url)
        except Exception as e:
            return Health.down(url=self._url).with_exception(e)


class HealthIndicatorRegistry:
    """
    Registry for health indicators.

    Allows dynamic registration of health checks and provides
    aggregated system health.
    """

    def __init__(self) -> None:
        self._indicators: dict[str, HealthIndicator] = {}
        self._timeout_seconds: float = 10.0

    def register(
        self,
        indicator: HealthIndicator,
        name: Optional[str] = None,
    ) -> "HealthIndicatorRegistry":
        """
        Register a health indicator.

        Args:
            indicator: The health indicator
            name: Override name (defaults to indicator.name)

        Returns:
            Self for chaining
        """
        key = name or indicator.name
        self._indicators[key] = indicator
        logger.debug(f"Registered health indicator: {key}")
        return self

    def unregister(self, name: str) -> bool:
        """
        Unregister a health indicator.

        Args:
            name: Indicator name

        Returns:
            True if removed
        """
        if name in self._indicators:
            del self._indicators[name]
            return True
        return False

    def get(self, name: str) -> Optional[HealthIndicator]:
        """Get a specific indicator by name."""
        return self._indicators.get(name)

    def list_indicators(self) -> list[str]:
        """List all registered indicator names."""
        return list(self._indicators.keys())

    async def check(self, name: str) -> Health:
        """
        Run a specific health check.

        Args:
            name: Indicator name

        Returns:
            Health result
        """
        indicator = self._indicators.get(name)
        if indicator is None:
            return Health.unknown(error=f"Unknown indicator: {name}")

        try:
            return await asyncio.wait_for(
                indicator.health(),
                timeout=self._timeout_seconds,
            )
        except TimeoutError:
            return Health.down(error="Health check timeout")
        except Exception as e:
            return Health.down().with_exception(e)

    async def check_all(self) -> Health:
        """
        Run all health checks and aggregate results.

        Returns:
            Aggregated Health with all components
        """
        if not self._indicators:
            return Health.up()

        # Run all checks concurrently
        tasks = {
            name: asyncio.create_task(
                asyncio.wait_for(
                    indicator.health(),
                    timeout=self._timeout_seconds,
                )
            )
            for name, indicator in self._indicators.items()
        }

        components: dict[str, Health] = {}
        statuses: list[HealthStatus] = []

        for name, task in tasks.items():
            try:
                health = await task
                components[name] = health
                statuses.append(health.status)
            except TimeoutError:
                health = Health.down(error="Health check timeout")
                components[name] = health
                statuses.append(HealthStatus.DOWN)
            except Exception as e:
                health = Health.down().with_exception(e)
                components[name] = health
                statuses.append(HealthStatus.DOWN)

        # Aggregate status (worst of all)
        overall_status = HealthStatus.worst(*statuses) if statuses else HealthStatus.UP

        return Health(
            status=overall_status,
            components=components,
            details={
                "checked_at": datetime.now(UTC).isoformat(),
                "component_count": len(components),
            },
        )

    async def liveness(self) -> Health:
        """
        Kubernetes liveness probe.

        Returns UP if the application is running.
        This is a lightweight check - don't include dependency checks.
        """
        return Health.up(timestamp=datetime.now(UTC).isoformat())

    async def readiness(self) -> Health:
        """
        Kubernetes readiness probe.

        Returns UP if the application can receive traffic.
        Includes critical dependency checks.
        """
        return await self.check_all()


# Global registry instance
_registry: Optional[HealthIndicatorRegistry] = None


def get_health_registry() -> HealthIndicatorRegistry:
    """Get or create the global health indicator registry."""
    global _registry
    if _registry is None:
        _registry = HealthIndicatorRegistry()
        # Register default indicators
        _registry.register(PingHealthIndicator(), "ping")
        _registry.register(DiskSpaceHealthIndicator(), "diskSpace")
    return _registry


def set_health_registry(registry: HealthIndicatorRegistry) -> None:
    """Set a custom health indicator registry."""
    global _registry
    _registry = registry


# Re-export commonly used classes
__all__ = [
    "Health",
    "HealthStatus",
    "HealthIndicator",
    "HealthIndicatorRegistry",
    "get_health_registry",
    "set_health_registry",
    "PingHealthIndicator",
    "DiskSpaceHealthIndicator",
    "MemoryHealthIndicator",
    "Neo4jHealthIndicator",
    "RedisHealthIndicator",
    "LLMHealthIndicator",
    "HttpHealthIndicator",
]
