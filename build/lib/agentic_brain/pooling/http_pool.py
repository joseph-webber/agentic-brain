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
HTTP connection pool implementation with circuit breaker.

Provides HTTP connection pooling with:
- Keep-alive connections per host
- Retry with exponential backoff
- Circuit breaker pattern
- Request timeouts

Example:
    >>> from agentic_brain.pooling import HttpPool, HttpPoolConfig
    >>>
    >>> config = HttpPoolConfig(
    ...     pool_size=100,
    ...     timeout=30.0
    ... )
    >>> pool = HttpPool(config)
    >>> await pool.startup()
    >>>
    >>> response = await pool.get("https://api.example.com/data")
    >>>
    >>> await pool.shutdown()
"""

from __future__ import annotations

import asyncio
import logging
import os
import random
import time
from dataclasses import dataclass, field
from enum import Enum
from typing import Any

logger = logging.getLogger(__name__)


class CircuitState(Enum):
    """Circuit breaker states."""

    CLOSED = "closed"  # Normal operation
    OPEN = "open"  # Failing, reject requests
    HALF_OPEN = "half_open"  # Testing if recovered


@dataclass
class HttpPoolConfig:
    """
    Configuration for HTTP connection pool.

    Attributes:
        pool_size: Maximum connections per host
        timeout: Default request timeout (seconds)
        connect_timeout: Connection establishment timeout (seconds)
        keepalive_timeout: Keep-alive timeout for idle connections (seconds)
        max_retries: Maximum retry attempts
        retry_base_delay: Base delay for exponential backoff (seconds)
        retry_max_delay: Maximum retry delay (seconds)
        circuit_failure_threshold: Failures before opening circuit
        circuit_recovery_timeout: Time before trying half-open (seconds)

    Environment Variables:
        HTTP_POOL_SIZE: Override pool_size
        CONNECTION_TIMEOUT: Override timeout
    """

    pool_size: int = 100
    timeout: float = 30.0
    connect_timeout: float = 10.0
    keepalive_timeout: float = 60.0
    max_retries: int = 3
    retry_base_delay: float = 0.5
    retry_max_delay: float = 30.0
    circuit_failure_threshold: int = 5
    circuit_recovery_timeout: float = 30.0

    def __post_init__(self) -> None:
        """Load from environment variables if set."""
        if pool_size := os.environ.get("HTTP_POOL_SIZE"):
            self.pool_size = int(pool_size)

        if timeout := os.environ.get("CONNECTION_TIMEOUT"):
            self.timeout = float(timeout)


@dataclass
class CircuitBreaker:
    """
    Circuit breaker for a single host.

    Implements the circuit breaker pattern to prevent
    cascading failures when a host is unavailable.

    States:
    - CLOSED: Normal operation, requests allowed
    - OPEN: Host failing, requests rejected
    - HALF_OPEN: Testing recovery, one request allowed
    """

    host: str
    failure_threshold: int = 5
    recovery_timeout: float = 30.0
    state: CircuitState = CircuitState.CLOSED
    failure_count: int = 0
    last_failure_time: float = 0.0
    success_count: int = 0

    def record_success(self) -> None:
        """Record a successful request."""
        if self.state == CircuitState.HALF_OPEN:
            self.success_count += 1
            if self.success_count >= 3:
                # Recovered, close circuit
                logger.info(f"Circuit closed for {self.host}")
                self.state = CircuitState.CLOSED
                self.failure_count = 0
                self.success_count = 0
        elif self.state == CircuitState.CLOSED:
            self.failure_count = 0

    def record_failure(self) -> None:
        """Record a failed request."""
        self.failure_count += 1
        self.last_failure_time = time.time()
        self.success_count = 0

        if self.state == CircuitState.HALF_OPEN:
            # Failed during recovery, reopen
            logger.warning(f"Circuit reopened for {self.host}")
            self.state = CircuitState.OPEN
        elif (
            self.state == CircuitState.CLOSED
            and self.failure_count >= self.failure_threshold
        ):
            # Too many failures, open circuit
            logger.warning(
                f"Circuit opened for {self.host} after {self.failure_count} failures"
            )
            self.state = CircuitState.OPEN

    def can_execute(self) -> bool:
        """Check if request can be executed."""
        if self.state == CircuitState.CLOSED:
            return True

        if self.state == CircuitState.OPEN:
            # Check if recovery timeout elapsed
            if time.time() - self.last_failure_time >= self.recovery_timeout:
                logger.info(f"Circuit half-open for {self.host}")
                self.state = CircuitState.HALF_OPEN
                return True
            return False

        # HALF_OPEN state - allow request to test recovery
        return True


@dataclass
class HttpPoolMetrics:
    """
    HTTP pool metrics.

    Attributes:
        total_requests: Total HTTP requests made
        successful_requests: Number of successful requests
        failed_requests: Number of failed requests
        retried_requests: Number of requests that were retried
        circuit_rejections: Requests rejected by circuit breaker
        average_response_time: Average response time (ms)
    """

    total_requests: int = 0
    successful_requests: int = 0
    failed_requests: int = 0
    retried_requests: int = 0
    circuit_rejections: int = 0
    average_response_time: float = 0.0
    _response_times: list[float] = field(default_factory=list)

    def record_request(self, duration_ms: float, success: bool) -> None:
        """Record a request."""
        self.total_requests += 1

        if success:
            self.successful_requests += 1
            self._response_times.append(duration_ms)
            # Keep only last 1000
            if len(self._response_times) > 1000:
                self._response_times = self._response_times[-1000:]
            self.average_response_time = sum(self._response_times) / len(
                self._response_times
            )
        else:
            self.failed_requests += 1


@dataclass
class HttpResponse:
    """
    HTTP response wrapper.

    Attributes:
        status: HTTP status code
        headers: Response headers
        body: Response body (bytes)
        text: Response body as text (lazy loaded)
        json_data: Response body as JSON (lazy loaded)
        elapsed_ms: Request duration in milliseconds
    """

    status: int
    headers: dict[str, str]
    body: bytes
    elapsed_ms: float
    _text: str | None = None
    _json: Any | None = None

    @property
    def ok(self) -> bool:
        """Check if response status is successful (2xx)."""
        return 200 <= self.status < 300

    @property
    def text(self) -> str:
        """Get response body as text."""
        if self._text is None:
            self._text = self.body.decode("utf-8", errors="replace")
        return self._text

    @property
    def json(self) -> Any:
        """Get response body as JSON."""
        if self._json is None:
            import json

            self._json = json.loads(self.body)
        return self._json


class HttpPool:
    """
    HTTP connection pool with circuit breaker.

    Provides efficient HTTP connection management with:
    - Connection pooling per host
    - Keep-alive connections
    - Automatic retry with exponential backoff
    - Circuit breaker pattern for fault tolerance

    Example:
        >>> pool = HttpPool(HttpPoolConfig(pool_size=100))
        >>> await pool.startup()
        >>>
        >>> # Simple GET
        >>> response = await pool.get("https://api.example.com/data")
        >>> print(response.json)
        >>>
        >>> # POST with JSON
        >>> response = await pool.post(
        ...     "https://api.example.com/create",
        ...     json={"name": "test"}
        ... )
        >>>
        >>> await pool.shutdown()
    """

    def __init__(self, config: HttpPoolConfig | None = None) -> None:
        """
        Initialize HTTP pool.

        Args:
            config: Pool configuration
        """
        self.config = config or HttpPoolConfig()
        self._session = None
        self._circuit_breakers: dict[str, CircuitBreaker] = {}
        self._metrics = HttpPoolMetrics()
        self._started = False
        self._lock = asyncio.Lock()

    @property
    def metrics(self) -> HttpPoolMetrics:
        """Get current pool metrics."""
        return self._metrics

    @property
    def is_started(self) -> bool:
        """Check if pool is started."""
        return self._started

    async def startup(self) -> None:
        """
        Start the HTTP pool.

        Creates the aiohttp ClientSession with connection pooling.
        """
        if self._started:
            logger.warning("HTTP pool already started")
            return

        try:
            import aiohttp
        except ImportError:
            logger.error("aiohttp package not installed. Run: pip install aiohttp")
            raise

        logger.info(f"Starting HTTP pool: pool_size={self.config.pool_size}")

        # Create connection pool
        connector = aiohttp.TCPConnector(
            limit=self.config.pool_size,
            limit_per_host=self.config.pool_size // 4,
            ttl_dns_cache=300,
            keepalive_timeout=self.config.keepalive_timeout,
        )

        timeout = aiohttp.ClientTimeout(
            total=self.config.timeout,
            connect=self.config.connect_timeout,
        )

        self._session = aiohttp.ClientSession(
            connector=connector,
            timeout=timeout,
        )

        self._started = True
        logger.info("HTTP pool started successfully")

    async def shutdown(self) -> None:
        """
        Shutdown the HTTP pool.

        Closes all connections and releases resources.
        """
        if not self._started:
            return

        logger.info("Shutting down HTTP pool...")

        if self._session:
            await self._session.close()
            self._session = None

        self._started = False
        logger.info("HTTP pool shutdown complete")

    def _get_host(self, url: str) -> str:
        """Extract host from URL."""
        from urllib.parse import urlparse

        parsed = urlparse(url)
        return parsed.netloc

    def _get_circuit_breaker(self, host: str) -> CircuitBreaker:
        """Get or create circuit breaker for host."""
        if host not in self._circuit_breakers:
            self._circuit_breakers[host] = CircuitBreaker(
                host=host,
                failure_threshold=self.config.circuit_failure_threshold,
                recovery_timeout=self.config.circuit_recovery_timeout,
            )
        return self._circuit_breakers[host]

    async def _request(
        self,
        method: str,
        url: str,
        **kwargs,
    ) -> HttpResponse:
        """
        Make an HTTP request with retry and circuit breaker.

        Args:
            method: HTTP method
            url: Request URL
            **kwargs: Additional arguments for aiohttp

        Returns:
            HttpResponse object

        Raises:
            RuntimeError: If pool not started
            aiohttp.ClientError: If request fails after retries
        """
        if not self._started or not self._session:
            raise RuntimeError("HTTP pool not started")

        host = self._get_host(url)
        circuit = self._get_circuit_breaker(host)

        # Check circuit breaker
        if not circuit.can_execute():
            self._metrics.circuit_rejections += 1
            raise RuntimeError(f"Circuit breaker open for {host}")

        last_error = None

        for attempt in range(self.config.max_retries + 1):
            try:
                start_time = time.time()

                async with self._session.request(method, url, **kwargs) as response:
                    body = await response.read()
                    elapsed_ms = (time.time() - start_time) * 1000

                    # Record success
                    circuit.record_success()
                    self._metrics.record_request(elapsed_ms, True)

                    return HttpResponse(
                        status=response.status,
                        headers=dict(response.headers),
                        body=body,
                        elapsed_ms=elapsed_ms,
                    )

            except Exception as e:
                last_error = e
                circuit.record_failure()

                if attempt < self.config.max_retries:
                    # Calculate backoff delay
                    delay = min(
                        self.config.retry_base_delay * (2**attempt)
                        + random.uniform(0, 0.1),
                        self.config.retry_max_delay,
                    )
                    self._metrics.retried_requests += 1
                    logger.warning(
                        f"Request failed, retrying in {delay:.2f}s: {method} {url} - {e}"
                    )
                    await asyncio.sleep(delay)

        # All retries failed
        self._metrics.record_request(0, False)
        raise last_error or RuntimeError(f"Request failed: {method} {url}")

    async def get(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        params: dict[str, Any] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """
        Make a GET request.

        Args:
            url: Request URL
            headers: Request headers
            params: Query parameters
            timeout: Request timeout override

        Returns:
            HttpResponse object
        """
        import aiohttp

        kwargs = {}
        if headers:
            kwargs["headers"] = headers
        if params:
            kwargs["params"] = params
        if timeout:
            kwargs["timeout"] = aiohttp.ClientTimeout(total=timeout)

        return await self._request("GET", url, **kwargs)

    async def post(
        self,
        url: str,
        data: Any | None = None,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """
        Make a POST request.

        Args:
            url: Request URL
            data: Form data
            json: JSON data
            headers: Request headers
            timeout: Request timeout override

        Returns:
            HttpResponse object
        """
        import aiohttp

        kwargs = {}
        if data:
            kwargs["data"] = data
        if json:
            kwargs["json"] = json
        if headers:
            kwargs["headers"] = headers
        if timeout:
            kwargs["timeout"] = aiohttp.ClientTimeout(total=timeout)

        return await self._request("POST", url, **kwargs)

    async def put(
        self,
        url: str,
        data: Any | None = None,
        json: Any | None = None,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """
        Make a PUT request.

        Args:
            url: Request URL
            data: Form data
            json: JSON data
            headers: Request headers
            timeout: Request timeout override

        Returns:
            HttpResponse object
        """
        import aiohttp

        kwargs = {}
        if data:
            kwargs["data"] = data
        if json:
            kwargs["json"] = json
        if headers:
            kwargs["headers"] = headers
        if timeout:
            kwargs["timeout"] = aiohttp.ClientTimeout(total=timeout)

        return await self._request("PUT", url, **kwargs)

    async def delete(
        self,
        url: str,
        headers: dict[str, str] | None = None,
        timeout: float | None = None,
    ) -> HttpResponse:
        """
        Make a DELETE request.

        Args:
            url: Request URL
            headers: Request headers
            timeout: Request timeout override

        Returns:
            HttpResponse object
        """
        import aiohttp

        kwargs = {}
        if headers:
            kwargs["headers"] = headers
        if timeout:
            kwargs["timeout"] = aiohttp.ClientTimeout(total=timeout)

        return await self._request("DELETE", url, **kwargs)

    async def health_check(self) -> dict[str, Any]:
        """
        Perform a health check on the pool.

        Returns:
            Health status dictionary
        """
        if not self._started:
            return {
                "healthy": False,
                "started": False,
                "error": "Pool not started",
            }

        # Get circuit breaker stats
        circuits = {}
        for host, circuit in self._circuit_breakers.items():
            circuits[host] = {
                "state": circuit.state.value,
                "failures": circuit.failure_count,
            }

        return {
            "healthy": True,
            "started": True,
            "pool_size": self.config.pool_size,
            "circuit_breakers": circuits,
            "metrics": {
                "total_requests": self._metrics.total_requests,
                "successful_requests": self._metrics.successful_requests,
                "failed_requests": self._metrics.failed_requests,
                "retried_requests": self._metrics.retried_requests,
                "circuit_rejections": self._metrics.circuit_rejections,
                "avg_response_ms": round(self._metrics.average_response_time, 2),
            },
        }


# Fallback for direct HTTP requests without pooling
class DirectHttpClient:
    """
    Direct HTTP client without pooling.

    Use as a fallback when pooling is not configured or needed.

    Example:
        >>> client = DirectHttpClient()
        >>> response = await client.get("https://api.example.com")
    """

    def __init__(self, timeout: float = 30.0) -> None:
        """Initialize direct client."""
        self._timeout = timeout

    async def get(self, url: str, **kwargs) -> HttpResponse:
        """Make a GET request."""
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=kwargs.pop("timeout", self._timeout))

        async with aiohttp.ClientSession(timeout=timeout) as session:
            start_time = time.time()
            async with session.get(url, **kwargs) as response:
                body = await response.read()
                elapsed_ms = (time.time() - start_time) * 1000

                return HttpResponse(
                    status=response.status,
                    headers=dict(response.headers),
                    body=body,
                    elapsed_ms=elapsed_ms,
                )

    async def post(self, url: str, **kwargs) -> HttpResponse:
        """Make a POST request."""
        import aiohttp

        timeout = aiohttp.ClientTimeout(total=kwargs.pop("timeout", self._timeout))

        async with aiohttp.ClientSession(timeout=timeout) as session:
            start_time = time.time()
            async with session.post(url, **kwargs) as response:
                body = await response.read()
                elapsed_ms = (time.time() - start_time) * 1000

                return HttpResponse(
                    status=response.status,
                    headers=dict(response.headers),
                    body=body,
                    elapsed_ms=elapsed_ms,
                )
