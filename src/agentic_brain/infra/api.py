# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber
#
# Licensed under the Apache License, Version 2.0 ("License");
# you may not use this file except in compliance with the License.
# You may obtain a copy of the License at
#
#     http://www.apache.org/licenses/LICENSE-2.0

"""
Health endpoint integration for agentic-brain API.

Add this to your FastAPI app to expose infrastructure health:

```python
from fastapi import FastAPI
from agentic_brain.infra.api import setup_health_endpoints

app = FastAPI()
setup_health_endpoints(app)
```

Endpoints:
- GET /health - Quick health check
- GET /infra/health - Detailed infrastructure status
- GET /infra/health/redis - Redis status only
- GET /infra/health/neo4j - Neo4j status only
- GET /infra/health/redpanda - Redpanda status only
"""

import logging
from typing import Any, Dict

from fastapi import FastAPI, HTTPException

logger = logging.getLogger(__name__)


def setup_health_endpoints(app: FastAPI):
    """
    Set up health endpoints on a FastAPI app.

    Args:
        app: FastAPI application instance
    """
    from agentic_brain.infra.health_monitor import HealthMonitor

    # Initialize monitor
    monitor = HealthMonitor()

    @app.on_event("startup")
    async def startup_health_monitor():
        """Initialize health monitor on startup."""
        await monitor.initialize()
        logger.info("Health monitor initialized")

    @app.on_event("shutdown")
    async def shutdown_health_monitor():
        """Clean up on shutdown."""
        await monitor.close()
        logger.info("Health monitor stopped")

    # === Quick Health Check ===

    @app.get("/health")
    async def quick_health_check() -> Dict[str, Any]:
        """Quick health check endpoint.

        Returns 200 if all services are healthy, 503 otherwise.
        """
        await monitor.check_all()

        if monitor.all_healthy:
            return {
                "status": "healthy",
                "services": {
                    name: health.status.value
                    for name, health in monitor.health_status.items()
                },
            }
        else:
            raise HTTPException(
                status_code=503,
                detail={
                    "status": "unhealthy",
                    "services": {
                        name: health.status.value
                        for name, health in monitor.health_status.items()
                    },
                },
            )

    # === Detailed Infrastructure Health ===

    @app.get("/infra/health")
    async def infrastructure_health() -> Dict[str, Any]:
        """Detailed infrastructure health status.

        Returns comprehensive health information for all services.
        """
        await monitor.check_all()

        return {
            "status": "healthy" if monitor.all_healthy else "unhealthy",
            "timestamp": monitor.health_status["redis"].last_check.isoformat(),
            "services": monitor.get_status_dict(),
        }

    # === Individual Service Health ===

    @app.get("/infra/health/redis")
    async def redis_health() -> Dict[str, Any]:
        """Redis health status."""
        await monitor.check_redis()
        health = monitor.health_status["redis"]

        return {
            "service": "redis",
            "status": health.status.value,
            "timestamp": health.last_check.isoformat(),
            "response_time_ms": health.response_time_ms,
            "error": health.error,
            "restart_count": health.restart_count,
        }

    @app.get("/infra/health/neo4j")
    async def neo4j_health() -> Dict[str, Any]:
        """Neo4j health status."""
        await monitor.check_neo4j()
        health = monitor.health_status["neo4j"]

        return {
            "service": "neo4j",
            "status": health.status.value,
            "timestamp": health.last_check.isoformat(),
            "response_time_ms": health.response_time_ms,
            "error": health.error,
            "restart_count": health.restart_count,
        }

    @app.get("/infra/health/redpanda")
    async def redpanda_health() -> Dict[str, Any]:
        """Redpanda health status."""
        await monitor.check_redpanda()
        health = monitor.health_status["redpanda"]

        return {
            "service": "redpanda",
            "status": health.status.value,
            "timestamp": health.last_check.isoformat(),
            "response_time_ms": health.response_time_ms,
            "error": health.error,
            "restart_count": health.restart_count,
        }

    # === Liveness and Readiness Probes ===

    @app.get("/healthz")
    async def liveness_probe() -> Dict[str, str]:
        """Kubernetes liveness probe.

        Returns 200 if the application is running.
        """
        return {"status": "alive"}

    @app.get("/readyz")
    async def readiness_probe() -> Dict[str, Any]:
        """Kubernetes readiness probe.

        Returns 200 if the application is ready to serve traffic.
        """
        await monitor.check_all()

        if monitor.all_healthy:
            return {"status": "ready"}
        else:
            raise HTTPException(
                status_code=503,
                detail={"status": "not ready"},
            )

    logger.info("Health endpoints registered")

    return {
        "endpoints": [
            "GET /health - Quick health check",
            "GET /infra/health - Detailed infrastructure status",
            "GET /infra/health/redis - Redis status",
            "GET /infra/health/neo4j - Neo4j status",
            "GET /infra/health/redpanda - Redpanda status",
            "GET /healthz - Kubernetes liveness probe",
            "GET /readyz - Kubernetes readiness probe",
        ]
    }
