# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Infrastructure health monitoring with auto-restart capability.

Monitors Redis, Neo4j, and Redpanda continuously.
Automatically restarts any service that goes down.
Exposes health status via /infra/health endpoint.
"""

import asyncio
import logging
import time
from dataclasses import asdict, dataclass
from datetime import datetime
from enum import Enum, StrEnum
from typing import Any, Callable, Dict, Optional

import redis.asyncio as aioredis

try:
    from neo4j import AsyncDriver, Neo4jDriver, basic_auth

    NEO4J_AVAILABLE = True
except ImportError:  # pragma: no cover
    AsyncDriver = None  # type: ignore
    Neo4jDriver = None  # type: ignore
    basic_auth = None  # type: ignore
    NEO4J_AVAILABLE = False

import docker

logger = logging.getLogger(__name__)


class ServiceStatus(StrEnum):
    """Service health status."""

    HEALTHY = "healthy"
    UNHEALTHY = "unhealthy"
    RESTARTING = "restarting"
    UNKNOWN = "unknown"


@dataclass
class ServiceHealth:
    """Health information for a service."""

    name: str
    status: ServiceStatus
    last_check: datetime
    check_timestamp: float
    response_time_ms: float
    error: Optional[str] = None
    restart_count: int = 0
    last_restart: Optional[datetime] = None
    uptime_seconds: Optional[float] = None

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary for JSON serialization."""
        return {
            "name": self.name,
            "status": self.status.value,
            "last_check": self.last_check.isoformat(),
            "check_timestamp": self.check_timestamp,
            "response_time_ms": self.response_time_ms,
            "error": self.error,
            "restart_count": self.restart_count,
            "last_restart": (
                self.last_restart.isoformat() if self.last_restart else None
            ),
            "uptime_seconds": self.uptime_seconds,
        }


class HealthMonitor:
    """
    Monitors infrastructure services and auto-restarts them if needed.

    Monitors:
    - Redis: via redis-cli ping
    - Neo4j: via Bolt protocol
    - Redpanda: via admin API

    Implements:
    - Continuous health checking
    - Auto-restart on failure
    - Event logging
    - REST API endpoint
    """

    def __init__(
        self,
        redis_host: str = "localhost",
        redis_port: int = 6379,
        redis_password: Optional[str] = None,
        neo4j_uri: str = "bolt://localhost:7687",
        neo4j_user: str = "neo4j",
        neo4j_password: Optional[str] = None,
        redpanda_host: str = "localhost",
        redpanda_port: int = 9644,
        check_interval: int = 30,
        max_restart_attempts: int = 5,
        restart_cooldown: int = 60,
        use_docker: bool = True,
    ):
        """
        Initialize health monitor.

        Args:
            redis_host: Redis host
            redis_port: Redis port
            redis_password: Redis password (optional)
            neo4j_uri: Neo4j Bolt URI
            neo4j_user: Neo4j username
            neo4j_password: Neo4j password
            redpanda_host: Redpanda host
            redpanda_port: Redpanda admin API port
            check_interval: Health check interval in seconds
            max_restart_attempts: Max restart attempts before giving up
            restart_cooldown: Cooldown between restart attempts (seconds)
            use_docker: Use Docker to manage services
        """
        self.redis_host = redis_host
        self.redis_port = redis_port
        self.redis_password = redis_password
        self.neo4j_uri = neo4j_uri
        self.neo4j_user = neo4j_user
        self.neo4j_password = neo4j_password
        self.redpanda_host = redpanda_host
        self.redpanda_port = redpanda_port
        self.check_interval = check_interval
        self.max_restart_attempts = max_restart_attempts
        self.restart_cooldown = restart_cooldown
        self.use_docker = use_docker

        self.redis_client = None
        self.neo4j_driver = None
        self.docker_client = None

        self.health_status: Dict[str, ServiceHealth] = {
            "redis": ServiceHealth(
                name="redis",
                status=ServiceStatus.UNKNOWN,
                last_check=datetime.now(),
                check_timestamp=time.time(),
                response_time_ms=0,
            ),
            "neo4j": ServiceHealth(
                name="neo4j",
                status=ServiceStatus.UNKNOWN,
                last_check=datetime.now(),
                check_timestamp=time.time(),
                response_time_ms=0,
            ),
            "redpanda": ServiceHealth(
                name="redpanda",
                status=ServiceStatus.UNKNOWN,
                last_check=datetime.now(),
                check_timestamp=time.time(),
                response_time_ms=0,
            ),
        }

        self.is_monitoring = False
        self.last_restart_attempt: Dict[str, float] = {}
        self.restart_callbacks: Dict[str, list] = {
            "redis": [],
            "neo4j": [],
            "redpanda": [],
        }

    async def initialize(self):
        """Initialize connections to all services."""
        try:
            # Initialize Redis
            if self.redis_password:
                redis_url = f"redis://:{self.redis_password}@{self.redis_host}:{self.redis_port}/0"
            else:
                redis_url = f"redis://{self.redis_host}:{self.redis_port}/0"

            self.redis_client = await aioredis.from_url(redis_url)
            logger.info("Redis client initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Redis client: {e}")

        if not NEO4J_AVAILABLE:
            logger.info("neo4j driver not installed; skipping Neo4j health monitoring")
        else:
            try:
                # Initialize Neo4j
                self.neo4j_driver = Neo4jDriver(
                    self.neo4j_uri,
                    auth=basic_auth(self.neo4j_user, self.neo4j_password),
                )
                logger.info("Neo4j driver initialized")
            except Exception as e:
                logger.warning(f"Could not initialize Neo4j driver: {e}")

        try:
            # Initialize Docker client
            if self.use_docker:
                self.docker_client = docker.from_env()
                logger.info("Docker client initialized")
        except Exception as e:
            logger.warning(f"Could not initialize Docker client: {e}")

    async def check_redis(self) -> ServiceHealth:
        """Check Redis health."""
        start_time = time.time()
        health = self.health_status["redis"]

        try:
            if self.redis_client:
                await self.redis_client.ping()
                response_time = (time.time() - start_time) * 1000
                health.status = ServiceStatus.HEALTHY
                health.error = None
                health.response_time_ms = response_time
                logger.debug(f"Redis health check passed ({response_time:.1f}ms)")
            else:
                # Try raw connection
                reader, writer = await asyncio.open_connection(
                    self.redis_host, self.redis_port
                )
                writer.write(b"PING\r\n")
                await writer.drain()
                response = await reader.read(1024)
                writer.close()
                if b"+PONG" in response or b"PONG" in response:
                    response_time = (time.time() - start_time) * 1000
                    health.status = ServiceStatus.HEALTHY
                    health.error = None
                    health.response_time_ms = response_time
        except Exception as e:
            health.status = ServiceStatus.UNHEALTHY
            health.error = str(e)
            logger.warning(f"Redis health check failed: {e}")

        health.last_check = datetime.now()
        health.check_timestamp = time.time()
        return health

    async def check_neo4j(self) -> ServiceHealth:
        """Check Neo4j health."""
        start_time = time.time()
        health = self.health_status["neo4j"]

        if not NEO4J_AVAILABLE:
            health.status = ServiceStatus.UNKNOWN
            health.error = "neo4j python driver not installed"
            health.last_check = datetime.now()
            health.check_timestamp = time.time()
            return health

        try:
            if self.neo4j_driver:
                await self.neo4j_driver.verify_connectivity()
                response_time = (time.time() - start_time) * 1000
                health.status = ServiceStatus.HEALTHY
                health.error = None
                health.response_time_ms = response_time
                logger.debug(f"Neo4j health check passed ({response_time:.1f}ms)")
            else:
                health.status = ServiceStatus.UNKNOWN
                health.error = "Neo4j driver not initialized"
        except Exception as e:
            health.status = ServiceStatus.UNHEALTHY
            health.error = str(e)
            logger.warning(f"Neo4j health check failed: {e}")

        health.last_check = datetime.now()
        health.check_timestamp = time.time()
        return health

    async def check_redpanda(self) -> ServiceHealth:
        """Check Redpanda health."""
        start_time = time.time()
        health = self.health_status["redpanda"]

        try:
            import aiohttp

            async with aiohttp.ClientSession() as session:
                async with session.get(
                    f"http://{self.redpanda_host}:{self.redpanda_port}/v1/status/ready",
                    timeout=aiohttp.ClientTimeout(total=5),
                ) as resp:
                    if resp.status == 200:
                        response_time = (time.time() - start_time) * 1000
                        health.status = ServiceStatus.HEALTHY
                        health.error = None
                        health.response_time_ms = response_time
                        logger.debug(
                            f"Redpanda health check passed ({response_time:.1f}ms)"
                        )
                    else:
                        health.status = ServiceStatus.UNHEALTHY
                        health.error = f"HTTP {resp.status}"
        except Exception as e:
            health.status = ServiceStatus.UNHEALTHY
            health.error = str(e)
            logger.debug(f"Redpanda health check failed: {e}")

        health.last_check = datetime.now()
        health.check_timestamp = time.time()
        return health

    async def check_all(self) -> Dict[str, ServiceHealth]:
        """Check health of all services."""
        await asyncio.gather(
            self.check_redis(),
            self.check_neo4j(),
            self.check_redpanda(),
        )
        return self.health_status

    async def restart_service(self, service_name: str) -> bool:
        """
        Restart a service.

        Args:
            service_name: Name of service (redis, neo4j, redpanda)

        Returns:
            True if restart was successful
        """
        health = self.health_status.get(service_name)
        if not health:
            logger.warning(f"Unknown service: {service_name}")
            return False

        # Check cooldown
        now = time.time()
        last_attempt = self.last_restart_attempt.get(service_name, 0)
        if now - last_attempt < self.restart_cooldown:
            logger.info(f"Restart cooldown active for {service_name}")
            return False

        # Check restart limit
        if health.restart_count >= self.max_restart_attempts:
            logger.error(
                f"Max restart attempts ({self.max_restart_attempts}) "
                f"reached for {service_name}"
            )
            return False

        logger.info(f"Restarting service: {service_name}")
        health.status = ServiceStatus.RESTARTING

        try:
            if self.use_docker and self.docker_client:
                await self._restart_docker_service(service_name)
            else:
                await self._restart_native_service(service_name)

            health.status = ServiceStatus.HEALTHY
            health.restart_count += 1
            health.last_restart = datetime.now()
            self.last_restart_attempt[service_name] = now

            logger.info(f"Successfully restarted {service_name}")

            # Call callbacks
            for callback in self.restart_callbacks.get(service_name, []):
                try:
                    await callback(service_name)
                except Exception as e:
                    logger.error(f"Error in restart callback: {e}")

            return True

        except Exception as e:
            logger.error(f"Failed to restart {service_name}: {e}")
            health.status = ServiceStatus.UNHEALTHY
            health.error = str(e)
            return False

    async def _restart_docker_service(self, service_name: str):
        """Restart a Docker service."""
        loop = asyncio.get_event_loop()

        container_names = {
            "redis": "agentic-brain-redis",
            "neo4j": "agentic-brain-neo4j",
            "redpanda": "agentic-brain-redpanda",
        }

        container_name = container_names.get(service_name)
        if not container_name:
            raise ValueError(f"Unknown Docker container for {service_name}")

        def restart_container():
            try:
                container = self.docker_client.containers.get(container_name)
                container.restart(timeout=30)
                logger.info(f"Docker container {container_name} restarted")
            except Exception as e:
                logger.error(f"Failed to restart Docker container: {e}")
                raise

        await loop.run_in_executor(None, restart_container)
        await asyncio.sleep(5)  # Wait for service to start

    async def _restart_native_service(self, service_name: str):
        """Restart a native (non-Docker) service."""
        if service_name == "redis":
            import subprocess

            subprocess.run(["redis-cli", "shutdown"], check=False)
            await asyncio.sleep(1)
            subprocess.Popen(["redis-server"])
            await asyncio.sleep(2)
        elif service_name == "neo4j":
            logger.warning("Native Neo4j restart not supported")
        elif service_name == "redpanda":
            logger.warning("Native Redpanda restart not supported")

    def register_restart_callback(
        self,
        service_name: str,
        callback: Callable[[str], None],
    ):
        """
        Register a callback to be called when a service is restarted.

        Args:
            service_name: Name of service
            callback: Async callback function that receives service name
        """
        if service_name in self.restart_callbacks:
            self.restart_callbacks[service_name].append(callback)

    async def health_check_loop(self):
        """Main health check loop."""
        logger.info("Starting health check loop")
        self.is_monitoring = True

        while self.is_monitoring:
            try:
                # Check all services
                await self.check_all()

                # Check for unhealthy services and restart if needed
                for service_name, health in self.health_status.items():
                    if health.status == ServiceStatus.UNHEALTHY:
                        logger.warning(
                            f"Service {service_name} is unhealthy: {health.error}"
                        )
                        await self.restart_service(service_name)

                # Wait before next check
                await asyncio.sleep(self.check_interval)

            except Exception as e:
                logger.error(f"Error in health check loop: {e}")
                await asyncio.sleep(self.check_interval)

    async def start_monitoring(self):
        """Start background monitoring."""
        await self.initialize()
        await self.health_check_loop()

    def stop_monitoring(self):
        """Stop background monitoring."""
        self.is_monitoring = False
        logger.info("Health monitoring stopped")

    async def close(self):
        """Clean up resources."""
        self.is_monitoring = False

        if self.redis_client:
            await self.redis_client.close()

        if self.neo4j_driver:
            self.neo4j_driver.close()

    def get_status(self) -> Dict[str, ServiceHealth]:
        """Get current health status of all services."""
        return self.health_status

    def get_status_dict(self) -> Dict[str, Dict[str, Any]]:
        """Get health status as dictionary."""
        return {name: health.to_dict() for name, health in self.health_status.items()}

    @property
    def all_healthy(self) -> bool:
        """Check if all services are healthy."""
        return all(
            health.status == ServiceStatus.HEALTHY
            for health in self.health_status.values()
        )

    @property
    def any_unhealthy(self) -> bool:
        """Check if any services are unhealthy."""
        return any(
            health.status == ServiceStatus.UNHEALTHY
            for health in self.health_status.values()
        )
