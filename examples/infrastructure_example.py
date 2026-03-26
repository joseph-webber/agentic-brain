"""
Example: Using agentic-brain infrastructure in your application.

This file shows how to integrate the health monitor and event bridge
into your agentic-brain application.
"""

import asyncio
import logging

from agentic_brain.infra import HealthMonitor, RedisRedpandaBridge

logger = logging.getLogger(__name__)


class BrainInfrastructure:
    """
    Complete infrastructure management for agentic-brain.

    Combines:
    - Health monitoring
    - Service auto-restart
    - Event bridging
    """

    def __init__(
        self,
        enable_health_monitor: bool = True,
        enable_event_bridge: bool = True,
        check_interval: int = 30,
    ):
        """Initialize brain infrastructure."""
        self.enable_health_monitor = enable_health_monitor
        self.enable_event_bridge = enable_event_bridge
        self.check_interval = check_interval

        self.monitor = None
        self.bridge = None
        self._tasks = []

    async def initialize(self):
        """Initialize all infrastructure components."""
        logger.info("Initializing agentic-brain infrastructure...")

        # Initialize health monitor
        if self.enable_health_monitor:
            self.monitor = HealthMonitor(check_interval=self.check_interval)
            await self.monitor.initialize()
            logger.info("Health monitor initialized")

            # Register restart callbacks
            self.monitor.register_restart_callback("redis", self._on_redis_restart)
            self.monitor.register_restart_callback("neo4j", self._on_neo4j_restart)

        # Initialize event bridge
        if self.enable_event_bridge:
            self.bridge = RedisRedpandaBridge()
            await self.bridge.initialize()
            logger.info("Event bridge initialized")

            # Register event callbacks
            self.bridge.register_event_callback(
                "brain.llm.request", self._on_llm_request
            )
            self.bridge.register_event_callback(
                "brain.agents.state", self._on_agent_state
            )

        logger.info("Infrastructure initialization complete")

    async def start(self):
        """Start infrastructure monitoring and event bridge."""
        logger.info("Starting infrastructure...")

        if self.enable_health_monitor and self.monitor:
            # Start health monitoring in background
            task = asyncio.create_task(self.monitor.start_monitoring())
            self._tasks.append(task)
            logger.info("Health monitoring started")

        if self.enable_event_bridge and self.bridge:
            # Start event bridge in background
            await self.bridge.start()
            logger.info("Event bridge started")

        logger.info("Infrastructure running")

    async def stop(self):
        """Stop infrastructure monitoring and event bridge."""
        logger.info("Stopping infrastructure...")

        if self.monitor:
            self.monitor.stop_monitoring()

        if self.bridge:
            await self.bridge.stop()

        # Cancel background tasks
        for task in self._tasks:
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass

        logger.info("Infrastructure stopped")

    async def get_health(self):
        """Get current infrastructure health status."""
        if not self.monitor:
            return None

        return self.monitor.get_status_dict()

    # === Callbacks ===

    async def _on_redis_restart(self, service_name: str):
        """Handle Redis restart."""
        logger.warning(f"{service_name} was restarted - rebuilding state")
        # Rebuild cache
        # Restore subscriptions
        # Notify clients

    async def _on_neo4j_restart(self, service_name: str):
        """Handle Neo4j restart."""
        logger.warning(f"{service_name} was restarted - checking data integrity")
        # Check data integrity
        # Rebuild indexes if needed
        # Verify connections

    async def _on_llm_request(self, event):
        """Handle LLM request event."""
        logger.debug(f"LLM Request: {event.topic}")
        # Log request
        # Track metrics
        # Route to handler

    async def _on_agent_state(self, event):
        """Handle agent state change event."""
        logger.debug(f"Agent State Changed: {event.topic}")
        # Update agent dashboard
        # Trigger watchers
        # Log state transition


# === Usage Example ===


async def main():
    """Example usage of brain infrastructure."""

    # Create infrastructure manager
    infra = BrainInfrastructure(
        enable_health_monitor=True,
        enable_event_bridge=True,
        check_interval=30,
    )

    # Initialize
    await infra.initialize()

    # Start
    await infra.start()

    try:
        # Your application runs here
        for i in range(10):
            # Check health periodically
            health = await infra.get_health()
            logger.info(f"Health: {health}")

            await asyncio.sleep(10)

    except KeyboardInterrupt:
        logger.info("Interrupted by user")
    finally:
        # Clean shutdown
        await infra.stop()


# === FastAPI Integration ===


async def setup_with_fastapi(app):
    """Set up infrastructure with FastAPI app."""
    from contextlib import asynccontextmanager

    infra = BrainInfrastructure()

    @asynccontextmanager
    async def lifespan(app):
        # Startup
        await infra.initialize()
        await infra.start()
        yield
        # Shutdown
        await infra.stop()

    app.router.lifespan_context = lifespan

    # Add health endpoints
    from agentic_brain.infra.api import setup_health_endpoints

    setup_health_endpoints(app)

    return infra


# === Daemon Integration ===


async def setup_with_daemon():
    """Set up infrastructure for daemon process."""
    infra = BrainInfrastructure(
        enable_health_monitor=True,
        enable_event_bridge=True,
        check_interval=30,
    )

    await infra.initialize()
    await infra.start()

    # Run indefinitely
    try:
        while True:
            health = await infra.get_health()
            if health:
                logger.info(f"Status: {health}")
            await asyncio.sleep(60)
    except KeyboardInterrupt:
        logger.info("Daemon shutting down...")
        await infra.stop()


if __name__ == "__main__":
    logging.basicConfig(level=logging.INFO)
    asyncio.run(main())
