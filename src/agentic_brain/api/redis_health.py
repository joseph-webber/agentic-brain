# SPDX-License-Identifier: Apache-2.0
# Copyright 2024-2026 Joseph Webber <joseph.webber@me.com>
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
Redis connection and health check utilities for Agentic Brain.

Ensures Redis is ALWAYS available:
- Checks Redis connectivity on startup
- Auto-detects Redis issues
- Provides health check endpoint
- Enables pub/sub functionality
"""

import logging
import os
import subprocess
import time
from typing import Optional

logger = logging.getLogger(__name__)


class RedisHealthCheck:
    """Redis health check and auto-start utilities."""

    def __init__(self):
        """Initialize Redis health checker."""
        self.redis_host = os.getenv("REDIS_HOST", "localhost")
        self.redis_port = int(os.getenv("REDIS_PORT", "6379"))
        self.redis_password = os.getenv("REDIS_PASSWORD", "brain_secure_2024")
        self.redis_db = int(os.getenv("REDIS_DB", "0"))

    def check_redis_available(self) -> tuple[bool, str]:
        """
        Check if Redis is available.

        Returns:
            tuple[bool, str]: (is_available, status_message)
        """
        try:
            # Try to import redis
            import redis

            # Try to connect
            r = redis.Redis(
                host=self.redis_host,
                port=self.redis_port,
                password=self.redis_password,
                db=self.redis_db,
                socket_connect_timeout=5,
                socket_keepalive=True,
                health_check_interval=30,
            )
            r.ping()
            return True, "Redis is healthy and responding"
        except ImportError:
            return False, "redis-py not installed (pip install redis)"
        except Exception as e:
            return False, f"Redis connection failed: {str(e)}"

    def try_auto_start_redis(self) -> bool:
        """
        Attempt to auto-start Redis if not running.

        Returns:
            bool: True if Redis started successfully or was already running
        """
        # Check if already running
        is_available, _ = self.check_redis_available()
        if is_available:
            logger.info("✓ Redis is already running")
            return True

        logger.warning("Redis not available, attempting auto-start...")

        # Try docker-compose
        try:
            docker_compose_path = os.path.join(
                os.path.dirname(__file__), "..", "..", "docker-compose-redis.yml"
            )
            if os.path.exists(docker_compose_path):
                logger.info(f"Starting Redis via docker-compose: {docker_compose_path}")
                result = subprocess.run(
                    ["docker-compose", "-f", docker_compose_path, "up", "-d"],
                    capture_output=True,
                    text=True,
                    timeout=30,
                )
                if result.returncode == 0:
                    # Wait for Redis to be ready
                    logger.info("Waiting for Redis to be healthy...")
                    for _attempt in range(30):
                        time.sleep(1)
                        is_available, msg = self.check_redis_available()
                        if is_available:
                            logger.info(f"✓ Redis is now available: {msg}")
                            return True
                    logger.error("Redis started but did not become healthy")
                    return False
                else:
                    logger.error(f"docker-compose failed: {result.stderr}")
                    return False
        except Exception as e:
            logger.warning(f"Could not auto-start Redis via docker-compose: {e}")

        # Try direct redis-server command (if installed locally)
        try:
            logger.info("Attempting to start redis-server directly...")
            subprocess.Popen(
                ["redis-server", "--port", str(self.redis_port)],
                stdout=subprocess.DEVNULL,
                stderr=subprocess.DEVNULL,
            )
            time.sleep(2)
            is_available, msg = self.check_redis_available()
            if is_available:
                logger.info(f"✓ Redis started successfully: {msg}")
                return True
        except Exception as e:
            logger.warning(f"Could not auto-start redis-server: {e}")

        return False

    def get_redis_client(self):
        """
        Get a Redis client instance.

        Returns:
            redis.Redis: Redis client

        Raises:
            RuntimeError: If Redis is not available and cannot be started
        """
        try:
            import redis
        except ImportError:
            raise RuntimeError(
                "redis-py not installed. Install with: pip install redis"
            )

        is_available, msg = self.check_redis_available()
        if not is_available:
            logger.error(f"Redis not available: {msg}")
            if not self.try_auto_start_redis():
                raise RuntimeError(
                    f"Redis is not available and auto-start failed: {msg}. "
                    "Start Redis with: docker-compose -f docker-compose-redis.yml up -d"
                )

        return redis.Redis(
            host=self.redis_host,
            port=self.redis_port,
            password=self.redis_password,
            db=self.redis_db,
            socket_connect_timeout=5,
            socket_keepalive=True,
            health_check_interval=30,
        )

    def get_health_status(self) -> dict:
        """
        Get Redis health status for /health endpoint.

        Returns:
            dict: Health status with keys:
                - status: "ok", "degraded", or "down"
                - available: bool
                - message: status message
                - host: Redis host
                - port: Redis port
                - db: Redis database number
        """
        is_available, msg = self.check_redis_available()

        if is_available:
            try:
                import redis

                r = redis.Redis(
                    host=self.redis_host,
                    port=self.redis_port,
                    password=self.redis_password,
                    db=self.redis_db,
                    socket_connect_timeout=2,
                )
                info = r.info()
                return {
                    "status": "ok",
                    "available": True,
                    "message": "Redis is healthy",
                    "host": self.redis_host,
                    "port": self.redis_port,
                    "db": self.redis_db,
                    "memory_usage_mb": info.get("used_memory_human", "unknown"),
                    "connected_clients": info.get("connected_clients", 0),
                }
            except Exception as e:
                return {
                    "status": "degraded",
                    "available": False,
                    "message": f"Redis connected but degraded: {str(e)}",
                    "host": self.redis_host,
                    "port": self.redis_port,
                    "db": self.redis_db,
                }

        return {
            "status": "down",
            "available": False,
            "message": msg,
            "host": self.redis_host,
            "port": self.redis_port,
            "db": self.redis_db,
        }


# Global health checker instance
_redis_health_check: Optional[RedisHealthCheck] = None


def get_redis_health_checker() -> RedisHealthCheck:
    """Get or create the global Redis health checker instance."""
    global _redis_health_check
    if _redis_health_check is None:
        _redis_health_check = RedisHealthCheck()
    return _redis_health_check
